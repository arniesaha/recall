#!/usr/bin/env python3
"""
Daily Sync Workflow for Knowledge Graph
- Processes new Granola transcripts
- Reorganizes into folder structure (people/, projects/, team/, etc.)
- Deduplicates content (same meeting, different files)
- Triggers re-indexing via API

Run via cron: 0 6 * * * /usr/bin/python3 /home/Arnab/clawd/projects/note-rag/scripts/daily_sync.py
Or via n8n webhook
"""

import os
import re
import json
import shutil
import hashlib
import logging
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from difflib import SequenceMatcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/Arnab/clawd/projects/note-rag/logs/daily_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Paths
VAULT_PATH = Path("/home/Arnab/clawd/projects/note-rag/obsidian/work")
GRANOLA_PATH = VAULT_PATH / "Granola" / "Transcripts"
STATE_FILE = Path("/home/Arnab/clawd/projects/note-rag/data/sync_state.json")
DUPLICATES_LOG = Path("/home/Arnab/clawd/projects/note-rag/logs/duplicates.log")

# API Config - use k8s internal ClusterIP (external URLs are behind Cloudflare Access)
API_URL = os.environ.get("NOTE_RAG_API_URL", "http://10.43.12.249:8080")
API_TOKEN = os.environ.get("NOTE_RAG_API_TOKEN", "kg-api-token-change-me")

# Deduplication thresholds
TITLE_SIMILARITY_THRESHOLD = 0.85  # 85% similar titles = likely same meeting
CONTENT_SIMILARITY_THRESHOLD = 0.90  # 90% similar content = duplicate

# Known people (lowercase for matching)
KNOWN_PEOPLE = {
    'hitesh', 'suman', 'nikhil', 'suraj', 'rajat', 'dhanya', 'sriram',
    'vijay', 'vijayaragavan', 'mukund', 'varun', 'daniel', 'krishna',
    'sameer', 'pratham', 'aarshi', 'arshi', 'muni', 'muniraju', 'ben',
    'peter', 'chandru', 'anshul', 'kunal', 'mohit', 'tambu', 'hrithik',
    'dinesh', 'anbarasan', 'gopi', 'sankar', 'ankur', 'vanya', 'anuya'
}

# Category keywords
CATEGORY_PATTERNS = {
    '1on1': [
        r'^\s*\w+\s*[/<>]+\s*\w+',  # Person / Person format
        r'1[:\-]?1', r'one on one', r'1on1', r'catch-?up'
    ],
    'daily_standup': [
        r'daily', r'standup', r'stand-up', r'cadence',
        r'metastore.*(daily|sync)', r'(daily|sync).*metastore'
    ],
    'project': [
        r'lean\s*graph', r'bedrock', r'lakehouse', r'polaris',
        r'migration', r'reindex', r'context\s*store'
    ],
    'team': [
        r'sprint', r'planning', r'retro', r'retrospective',
        r'sync', r'weekly', r'bi-?weekly'
    ],
    'calibration': [
        r'calibration', r'performance.*review', r'promotion',
        r'rating', r'p[1-4]'
    ],
    'incident': [
        r'incident', r'outage', r'war\s*room', r'escalation', r'p[0-1]\s'
    ],
    'interview': [
        r'interview', r'hiring', r'candidate'
    ]
}


def load_state() -> Dict:
    """Load sync state (processed files and hashes)."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {'processed': {}, 'duplicates': {}, 'content_index': {}, 'last_run': None}


def save_state(state: Dict):
    """Save sync state."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state['last_run'] = datetime.now().isoformat()
    # Don't persist the indexes - they're rebuilt on load
    state_to_save = {k: v for k, v in state.items() if k not in ('granola_id_index',)}
    with open(STATE_FILE, 'w') as f:
        json.dump(state_to_save, f, indent=2)


def update_state_indexes(state: Dict, path_str: str, info: Dict, content_fp: str = None):
    """Update all state indexes after processing a file."""
    # Update granola_id index
    granola_id = info.get('granola_id', '')
    if granola_id:
        if 'granola_id_index' not in state:
            state['granola_id_index'] = {}
        state['granola_id_index'][granola_id] = {
            'path': path_str,
            'output': info.get('output', path_str),
            'content_len': info.get('content_len', 0)
        }
    
    # Update content index
    if content_fp:
        if 'content_index' not in state:
            state['content_index'] = {}
        state['content_index'][content_fp] = {
            'path': path_str,
            'output': info.get('output', path_str),
            'content_len': info.get('content_len', 0)
        }


def get_file_hash(path: Path) -> str:
    """Get MD5 hash of file content."""
    return hashlib.md5(path.read_bytes()).hexdigest()


def get_content_fingerprint(body: str) -> str:
    """Create a fingerprint of content for dedup (ignores whitespace variations)."""
    # Normalize: lowercase, remove extra whitespace, take first 2000 chars
    normalized = ' '.join(body.lower().split())[:2000]
    return hashlib.md5(normalized.encode()).hexdigest()


def similarity_ratio(a: str, b: str) -> float:
    """Calculate similarity ratio between two strings."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def normalize_title(title: str) -> str:
    """Normalize title for comparison."""
    # Remove common suffixes and noise
    title = re.sub(r'\s*-\s*Transcript$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*-\s*transcript-\d{4}-\d{2}-\d{2}.*$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*\(\d+\)$', '', title)  # Remove (2), (3) etc
    title = re.sub(r'\s+', ' ', title).strip()
    return title


def parse_frontmatter(content: str) -> Tuple[Dict, str]:
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith('---'):
        return {}, content
    
    try:
        end = content.index('---', 3)
        frontmatter_str = content[3:end].strip()
        body = content[end+3:].strip()
        
        # Simple YAML parsing (avoid dependency)
        frontmatter = {}
        current_key = None
        current_list = None
        
        for line in frontmatter_str.split('\n'):
            line = line.rstrip()
            if not line:
                continue
            
            # List item
            if line.startswith('  - '):
                if current_list is not None:
                    current_list.append(line[4:].strip())
                continue
            
            # Key-value
            if ':' in line:
                key, _, value = line.partition(':')
                key = key.strip()
                value = value.strip().strip('"')
                
                if value:
                    frontmatter[key] = value
                    current_list = None
                else:
                    frontmatter[key] = []
                    current_list = frontmatter[key]
                current_key = key
        
        return frontmatter, body
    except:
        return {}, content


def extract_people(frontmatter: Dict, body: str) -> List[str]:
    """Extract people mentioned in the meeting."""
    people = set()
    
    # From attendees
    for attendee in frontmatter.get('attendees', []):
        # Extract name from email or plain name
        if '@' in attendee:
            name = attendee.split('@')[0].replace('.', ' ').split()[0]
        else:
            name = attendee.split()[0]
        name = name.lower()
        if name in KNOWN_PEOPLE:
            people.add(name.title())
    
    # From title
    title = frontmatter.get('title', '').lower()
    for person in KNOWN_PEOPLE:
        if person in title:
            people.add(person.title())
    
    # From body (first 500 chars)
    body_lower = body[:500].lower()
    for person in KNOWN_PEOPLE:
        if re.search(rf'\b{person}\b', body_lower):
            people.add(person.title())
    
    return list(people)


def categorize_meeting(frontmatter: Dict, body: str) -> str:
    """Determine meeting category."""
    title = frontmatter.get('title', '').lower()
    meeting_type = frontmatter.get('type', '').lower()
    
    # Check each category pattern
    for category, patterns in CATEGORY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, title, re.IGNORECASE):
                return category
            if re.search(pattern, body[:500], re.IGNORECASE):
                return category
    
    # Default to 'other'
    return 'other'


def extract_date(frontmatter: Dict, filename: str) -> str:
    """Extract date from frontmatter or filename."""
    # From frontmatter
    created = frontmatter.get('created', '')
    if created:
        try:
            dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d')
        except:
            pass
    
    # From filename
    date_match = re.search(r'(\d{4})[/-]?(\d{2})[/-]?(\d{2})', filename)
    if date_match:
        return f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
    
    return datetime.now().strftime('%Y-%m-%d')


def slugify(text: str) -> str:
    """Convert text to safe filename slug."""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')[:60]


def extract_person_from_1on1(title: str) -> Optional[str]:
    """Extract person name from 1:1 title."""
    patterns = [
        r'^(.+?)\s*[/<>|]+\s*[Aa]rnab',
        r'^[Aa]rnab\s*[/<>|]+\s*(.+)',
        r'^(.+?)\s+[/<>|]+\s+',
    ]
    
    for pattern in patterns:
        match = re.match(pattern, title)
        if match:
            person = match.group(1).strip()
            # Clean up
            person = re.sub(r'\s*[-–]\s*\d+.*$', '', person)
            person = re.sub(r'\s*[-–]\s*H[12].*$', '', person, re.IGNORECASE)
            person = re.sub(r'\s*[-–]\s*Weekly.*$', '', person, re.IGNORECASE)
            person = re.sub(r'\s*[|/<>].*$', '', person)
            person = re.sub(r'^\(W\)\s*', '', person)
            person = re.sub(r'\s*-\s*Transcript$', '', person, re.IGNORECASE)
            return person.strip()
    
    return None


def determine_output_path(frontmatter: Dict, body: str, category: str, original_path: Path) -> Path:
    """Determine where to place the file."""
    title = frontmatter.get('title', original_path.stem)
    date = extract_date(frontmatter, original_path.name)
    slug = slugify(title.replace(' - Transcript', ''))
    
    if category == '1on1':
        person = extract_person_from_1on1(title)
        if person:
            person_slug = slugify(person)
            return VAULT_PATH / 'people' / person_slug / f"{date}-{slug}.md"
        return VAULT_PATH / 'people' / 'misc' / f"{date}-{slug}.md"
    
    elif category == 'daily_standup':
        if 'metastore' in title.lower():
            return VAULT_PATH / 'team' / 'metastore-daily' / f"{date}.md"
        elif 'lakehouse' in title.lower() or 'mdlh' in title.lower():
            return VAULT_PATH / 'team' / 'lakehouse-daily' / f"{date}.md"
        return VAULT_PATH / 'team' / 'daily' / f"{date}-{slug}.md"
    
    elif category == 'project':
        # Determine project
        title_lower = title.lower()
        if 'lean' in title_lower and 'graph' in title_lower:
            return VAULT_PATH / 'projects' / 'lean-graph' / f"{date}-{slug}.md"
        elif 'bedrock' in title_lower:
            return VAULT_PATH / 'projects' / 'bedrock' / f"{date}-{slug}.md"
        elif 'lakehouse' in title_lower or 'polaris' in title_lower:
            return VAULT_PATH / 'projects' / 'lakehouse' / f"{date}-{slug}.md"
        elif 'migration' in title_lower:
            return VAULT_PATH / 'projects' / 'migrations' / f"{date}-{slug}.md"
        return VAULT_PATH / 'projects' / 'other' / f"{date}-{slug}.md"
    
    elif category == 'team':
        return VAULT_PATH / 'team' / 'weekly' / f"{date}-{slug}.md"
    
    elif category == 'calibration':
        return VAULT_PATH / 'other' / f"{date}-{slug}.md"
    
    elif category == 'incident':
        return VAULT_PATH / 'incidents' / f"{date}-{slug}.md"
    
    elif category == 'interview':
        return VAULT_PATH / 'interviews' / f"{date}-{slug}.md"
    
    return VAULT_PATH / 'other' / f"{date}-{slug}.md"


def update_frontmatter(content: str, frontmatter: Dict, category: str, people: List[str], date: str) -> str:
    """Update frontmatter with additional metadata."""
    new_fm = {
        'title': frontmatter.get('title', '').replace(' - Transcript', ''),
        'date': date,
        'category': category,
        'people': people,
        'granola_id': frontmatter.get('granola_id', ''),
    }
    
    # Build new frontmatter
    lines = ['---']
    for key, value in new_fm.items():
        if isinstance(value, list):
            if value:
                lines.append(f'{key}:')
                for item in value:
                    lines.append(f'  - "{item}"')
            else:
                lines.append(f'{key}: []')
        else:
            lines.append(f'{key}: "{value}"')
    lines.append('---\n')
    
    # Get body (strip old frontmatter)
    _, body = parse_frontmatter(content)
    
    return '\n'.join(lines) + body


def find_duplicate(
    frontmatter: Dict, 
    body: str, 
    date: str, 
    state: Dict,
    current_path: Path
) -> Optional[Dict]:
    """
    Find existing duplicate based on:
    1. Same granola_id
    2. Same date + similar title
    3. Very similar content fingerprint
    
    Returns dict with 'path', 'reason', 'existing_content_len' if duplicate found.
    """
    granola_id = frontmatter.get('granola_id', '')
    title = normalize_title(frontmatter.get('title', ''))
    content_fp = get_content_fingerprint(body)
    
    # Build indexes if not present
    if 'content_index' not in state:
        state['content_index'] = {}
    if 'granola_id_index' not in state:
        # Build granola_id index from existing processed entries
        state['granola_id_index'] = {}
        for path_str, info in state['processed'].items():
            gid = info.get('granola_id', '')
            if gid:
                state['granola_id_index'][gid] = {
                    'path': path_str,
                    'output': info.get('output', path_str),
                    'content_len': info.get('content_len', 0)
                }
    
    # Check granola_id match (O(1) lookup via index)
    if granola_id and granola_id in state['granola_id_index']:
        existing = state['granola_id_index'][granola_id]
        if existing['path'] != str(current_path):
            return {
                'path': existing['path'],
                'output': existing['output'],
                'reason': 'same_granola_id',
                'existing_content_len': existing.get('content_len', 0)
            }
    
    # Check same date + similar title
    for path_str, info in state['processed'].items():
        if path_str == str(current_path):
            continue
        if info.get('date') == date:
            existing_title = normalize_title(info.get('title', ''))
            if similarity_ratio(title, existing_title) >= TITLE_SIMILARITY_THRESHOLD:
                return {
                    'path': path_str,
                    'output': info.get('output', path_str),
                    'reason': 'same_date_similar_title',
                    'existing_content_len': info.get('content_len', 0),
                    'similarity': similarity_ratio(title, existing_title)
                }
    
    # Check content fingerprint (catches renamed files)
    if content_fp in state['content_index']:
        existing = state['content_index'][content_fp]
        if existing['path'] != str(current_path):
            return {
                'path': existing['path'],
                'output': existing.get('output', existing['path']),
                'reason': 'same_content_fingerprint',
                'existing_content_len': existing.get('content_len', 0)
            }
    
    return None


def log_duplicate(original: Path, duplicate: Path, reason: str, action: str):
    """Log duplicate detection for review."""
    DUPLICATES_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(DUPLICATES_LOG, 'a') as f:
        f.write(f"{datetime.now().isoformat()} | {reason} | {action}\n")
        f.write(f"  Original:  {original}\n")
        f.write(f"  Duplicate: {duplicate}\n")
        f.write("\n")


def merge_content(existing_content: str, new_content: str) -> Tuple[str, bool]:
    """
    Merge two transcript contents intelligently.
    Returns (merged_content, was_merged).
    
    Strategy:
    - If one is clearly longer/more complete, use it
    - If similar length, check for unique sections and combine
    """
    _, existing_body = parse_frontmatter(existing_content)
    _, new_body = parse_frontmatter(new_content)
    
    existing_len = len(existing_body.strip())
    new_len = len(new_body.strip())
    
    # If new content is significantly longer (>20%), it's probably more complete
    if new_len > existing_len * 1.2:
        return new_content, True
    
    # If existing is longer or same, keep existing
    return existing_content, False


def process_file(path: Path, state: Dict, stats: Dict) -> Optional[Path]:
    """Process a single transcript file."""
    try:
        file_hash = get_file_hash(path)
        path_str = str(path)
        
        # Skip if already processed and unchanged
        if path_str in state['processed']:
            if state['processed'][path_str]['hash'] == file_hash:
                return None
        
        logger.info(f"Processing: {path.name}")
        
        # Read and parse
        content = path.read_text(encoding='utf-8')
        frontmatter, body = parse_frontmatter(content)
        
        # Extract metadata
        category = categorize_meeting(frontmatter, body)
        people = extract_people(frontmatter, body)
        date = extract_date(frontmatter, path.name)
        title = frontmatter.get('title', path.stem)
        granola_id = frontmatter.get('granola_id', '')
        content_fp = get_content_fingerprint(body)
        content_len = len(body.strip())
        
        # Check for duplicates
        duplicate = find_duplicate(frontmatter, body, date, state, path)
        
        if duplicate:
            existing_output = Path(duplicate['output'])
            
            # Decide: skip or merge
            if existing_output.exists():
                existing_content = existing_output.read_text(encoding='utf-8')
                merged, was_merged = merge_content(existing_content, content)
                
                if was_merged:
                    # New content is better - update existing file
                    new_content = update_frontmatter(content, frontmatter, category, people, date)
                    existing_output.write_text(new_content, encoding='utf-8')
                    log_duplicate(existing_output, path, duplicate['reason'], 'MERGED (new content longer)')
                    logger.info(f"  -> MERGED into {existing_output.relative_to(VAULT_PATH)} (new content longer)")
                    stats['merged'] += 1
                else:
                    # Existing is fine, skip
                    log_duplicate(existing_output, path, duplicate['reason'], 'SKIPPED (existing content adequate)')
                    logger.info(f"  -> SKIPPED (duplicate of {existing_output.name}, reason: {duplicate['reason']})")
                    stats['skipped_duplicates'] += 1
            else:
                # Existing file was deleted/moved, process normally
                logger.info(f"  -> Previous output missing, processing fresh")
        
            # Update state even for skipped files
            info = {
                'hash': file_hash,
                'output': str(existing_output),
                'category': category,
                'people': people,
                'date': date,
                'title': title,
                'granola_id': granola_id,
                'content_len': content_len,
                'duplicate_of': duplicate['path']
            }
            state['processed'][path_str] = info
            update_state_indexes(state, path_str, info, content_fp)
            return None
        
        # Not a duplicate - determine output path
        output_path = determine_output_path(frontmatter, body, category, path)
        
        # Skip if output would be same as input
        if output_path.resolve() == path.resolve():
            info = {
                'hash': file_hash, 
                'output': path_str,
                'category': category,
                'people': people,
                'date': date,
                'title': title,
                'granola_id': granola_id,
                'content_len': content_len
            }
            state['processed'][path_str] = info
            update_state_indexes(state, path_str, info, content_fp)
            return None
        
        # Check if output path already exists (another file already there)
        if output_path.exists() and str(output_path) not in [v.get('output') for v in state['processed'].values()]:
            # Check if existing file has same granola_id (means it's actually a duplicate we should merge)
            try:
                existing_content = output_path.read_text(encoding='utf-8')
                existing_fm, existing_body = parse_frontmatter(existing_content)
                existing_granola_id = existing_fm.get('granola_id', '')
                
                if granola_id and existing_granola_id == granola_id:
                    # Same meeting! Merge if new content is better
                    merged, was_merged = merge_content(existing_content, content)
                    if was_merged:
                        new_content = update_frontmatter(content, frontmatter, category, people, date)
                        output_path.write_text(new_content, encoding='utf-8')
                        logger.info(f"  -> MERGED into existing {output_path.name} (same granola_id, new content longer)")
                        stats['merged'] += 1
                    else:
                        logger.info(f"  -> SKIPPED (same granola_id as {output_path.name}, existing content adequate)")
                        stats['skipped_duplicates'] += 1
                    
                    # Update state
                    info = {
                        'hash': file_hash,
                        'output': str(output_path),
                        'category': category,
                        'people': people,
                        'date': date,
                        'title': title,
                        'granola_id': granola_id,
                        'content_len': content_len,
                        'duplicate_of': str(output_path)
                    }
                    state['processed'][path_str] = info
                    update_state_indexes(state, path_str, info, content_fp)
                    return None
                else:
                    # Genuine collision - different meetings mapped to same output path
                    # Log error and skip rather than creating -2 files
                    logger.error(f"  -> COLLISION: {path.name} would overwrite {output_path.name} (different granola_ids)")
                    logger.error(f"       Source granola_id: {granola_id}")
                    logger.error(f"       Existing granola_id: {existing_granola_id}")
                    stats['errors'] += 1
                    return None
            except Exception as e:
                logger.error(f"  -> Error checking existing file {output_path}: {e}")
                stats['errors'] += 1
                return None
        
        # Create directories
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Update content with new frontmatter
        new_content = update_frontmatter(content, frontmatter, category, people, date)
        
        # Write to new location
        output_path.write_text(new_content, encoding='utf-8')
        logger.info(f"  -> {output_path.relative_to(VAULT_PATH)}")
        
        # Update state
        info = {
            'hash': file_hash,
            'output': str(output_path),
            'category': category,
            'people': people,
            'date': date,
            'title': title,
            'granola_id': granola_id,
            'content_len': content_len
        }
        state['processed'][path_str] = info
        update_state_indexes(state, path_str, info, content_fp)
        
        stats['processed'] += 1
        return output_path
        
    except Exception as e:
        logger.error(f"Error processing {path}: {e}")
        stats['errors'] += 1
        return None


def find_new_files(state: Dict, hours_back: int = 24) -> List[Path]:
    """Find new or modified transcript files."""
    cutoff = datetime.now() - timedelta(hours=hours_back)
    new_files = []
    
    for path in GRANOLA_PATH.rglob('*.md'):
        # Check if modified recently or not in state
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        path_str = str(path)
        
        if path_str not in state['processed']:
            new_files.append(path)
        elif mtime > cutoff:
            # Check hash
            current_hash = get_file_hash(path)
            if state['processed'][path_str].get('hash') != current_hash:
                new_files.append(path)
    
    return new_files


def trigger_reindex():
    """Trigger knowledge graph reindexing (async)."""
    try:
        # Use /index/start endpoint (async) - returns job_id
        response = requests.post(
            f"{API_URL}/index/start",
            headers={
                'Authorization': f'Bearer {API_TOKEN}',
                'Content-Type': 'application/json'
            },
            json={'vault': 'work'},
            timeout=30
        )
        if response.ok:
            result = response.json()
            job_id = result.get('job_id', 'unknown')
            logger.info(f"Reindex started: job_id={job_id}")
            return True
        else:
            logger.error(f"Reindex failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Reindex error: {e}")
        return False


def cleanup_orphaned_outputs(state: Dict, stats: Dict):
    """Remove output files whose source no longer exists."""
    orphaned = []
    for path_str, info in list(state['processed'].items()):
        source = Path(path_str)
        output = Path(info.get('output', path_str))
        
        # If source was deleted but output exists
        if not source.exists() and output.exists() and source != output:
            # Check if it's a duplicate that points to same output
            is_shared_output = sum(1 for v in state['processed'].values() if v.get('output') == str(output)) > 1
            if not is_shared_output:
                orphaned.append((path_str, output))
    
    for path_str, output in orphaned:
        logger.info(f"Orphaned output (source deleted): {output}")
        # Don't delete automatically - just log for review
        stats['orphaned'] += 1


def main(full_scan: bool = False):
    """Main workflow."""
    logger.info("=" * 50)
    logger.info("Starting daily sync workflow")
    
    # Create logs directory
    Path('/home/Arnab/clawd/projects/note-rag/logs').mkdir(parents=True, exist_ok=True)
    
    # Load state
    state = load_state()
    logger.info(f"Last run: {state.get('last_run', 'never')}")
    
    # Stats tracking
    stats = {
        'processed': 0,
        'merged': 0,
        'skipped_duplicates': 0,
        'errors': 0,
        'orphaned': 0
    }
    
    # Find new files (look back 48 hours normally, or scan all for full_scan)
    hours_back = 8760 if full_scan else 48  # 1 year for full scan
    new_files = find_new_files(state, hours_back=hours_back)
    logger.info(f"Found {len(new_files)} new/modified files")
    
    if not new_files:
        logger.info("No new files to process")
        cleanup_orphaned_outputs(state, stats)
        save_state(state)
        return stats
    
    # Process each file
    for path in sorted(new_files):
        process_file(path, state, stats)
    
    # Cleanup check
    cleanup_orphaned_outputs(state, stats)
    
    # Save state
    save_state(state)
    
    # Log summary
    logger.info("-" * 30)
    logger.info(f"Summary:")
    logger.info(f"  Processed: {stats['processed']}")
    logger.info(f"  Merged: {stats['merged']}")
    logger.info(f"  Skipped (duplicates): {stats['skipped_duplicates']}")
    logger.info(f"  Errors: {stats['errors']}")
    logger.info(f"  Orphaned outputs: {stats['orphaned']}")
    
    # Trigger reindex if we processed files
    if stats['processed'] > 0 or stats['merged'] > 0:
        logger.info("Triggering reindex...")
        trigger_reindex()
    
    logger.info("Daily sync complete")
    return stats


if __name__ == '__main__':
    import sys
    full_scan = '--full' in sys.argv
    if full_scan:
        logger.info("Running FULL SCAN (all files)")
    main(full_scan=full_scan)
