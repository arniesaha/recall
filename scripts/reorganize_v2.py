#!/usr/bin/env python3
"""
Vault Reorganization v2
- Consolidates duplicate person folders
- Moves non-person content out of people/
- Merges daily summaries into people folders
- Improves categorization

Run with --dry-run first to preview changes.
"""

import os
import re
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict

# Paths
VAULT_PATH = Path("/home/Arnab/clawd/projects/recall/obsidian/work")
DAILY_NOTES_PATH = VAULT_PATH / "daily-notes"
PEOPLE_PATH = VAULT_PATH / "people"
INTERVIEWS_PATH = VAULT_PATH / "interviews"
PERFORMANCE_PATH = VAULT_PATH / "performance"
GRANOLA_PATH = VAULT_PATH / "Granola" / "Transcripts"

# Person name canonicalization (variant -> canonical)
PERSON_ALIASES = {
    # Vijay variants
    'vijay': 'vijayaragavan',
    'vijayaragavan-weekly-11': 'vijayaragavan',
    'vijayaragavan-vijayaragavan': 'vijayaragavan',
    
    # Dhanya variants
    'dhanya-kumar': 'dhanya',
    'dhanya-kumar-arnab': 'dhanya',
    
    # Krishna variants
    'krishna': 'krishnanunni',
    'krishnanunni-m': 'krishnanunni',
    'krishnanunni-m-and-arnab-saha': 'krishnanunni',
    
    # Nikhil variants
    'nikhil-m': 'nikhil',
    
    # Suman variants  
    'suman-p': 'suman',
    
    # Hitesh variants
    'hitesh-g': 'hitesh',
    
    # Tambu variants
    'thambu': 'tambu',
    
    # Chandru variants
    'chandru-metadata-lakehouse': 'chandru',
    
    # Anshul variants (but keep separate if different context)
    'anshul-dx': 'anshul',
    'anshul-epd-townhall': 'anshul',
    
    # Hritik/Hrithik variants
    'hritik': 'hrithik',
}

# Folders that should NOT be in people/ - move to appropriate location
NON_PERSON_FOLDERS = {
    # Interview stages -> interviews/
    'work-experience-deep-dive-epd': ('interviews', 'stages'),
    'standard-challenge-deep-dive': ('interviews', 'stages'),
    'rescheduled-work-experience-deep-dive-epd': ('interviews', 'stages'),
    
    # Performance -> performance/
    'h2-growth-conversation-arnab': ('performance', 'growth-conversations'),
    'calibration': ('performance', 'calibration'),
    
    # Companies/vendors -> cross-team/vendors/
    'aws': ('cross-team', 'vendors'),
    'databricks': ('cross-team', 'vendors'),
    'dbx': ('cross-team', 'vendors'),  # databricks shorthand
    'atlan': ('cross-team', 'company'),
    
    # Projects -> projects/
    'itau': ('projects', 'itau'),
    'metastore': ('projects', 'metastore'),
    'medidata': ('projects', 'medidata'),
    'platform': ('projects', 'platform'),
    
    # Team meetings -> team/
    'support': ('team', 'support'),
    
    # Misc introductions -> cross-team/
    'td-intro': ('cross-team', 'introductions'),
    'hm-intro': ('interviews', 'hm-intros'),
    
    # More projects
    'purple': ('projects', 'purple'),
    'hubspot': ('projects', 'hubspot'),
    'lh-linear-setup': ('projects', 'lakehouse'),
    'metadata-lakehouse-product': ('projects', 'lakehouse'),
    'dx': ('projects', 'developer-experience'),
    
    # Misc/catch-all
    'misc': ('other', 'misc'),
    'sync-w': ('other', 'misc'),  # Weird naming, probably catch-all
}

# Known people (canonical names, lowercase)
KNOWN_PEOPLE = {
    'aarshi', 'aayush', 'alok', 'anbarasan', 'ankit', 'anshul', 'arjit',
    'ben', 'bindu', 'birendra', 'chandru', 'daniel', 'dhanya', 'dinesh',
    'faisal', 'gopi', 'hitesh', 'hrithik', 'krishnanunni', 'kunal',
    'mohit', 'mukund', 'muni', 'muniraju', 'nikhil', 'peter', 'pratham',
    'rajat', 'sameer', 'sankar', 'sriram', 'suman', 'suraj', 'sushit',
    'tambu', 'tanmay', 'varun', 'vanya', 'vijayaragavan', 'anuya', 'ankur',
    'ayush', 'sid', 'arshi',
    # Added from unknown folder analysis
    'rohit', 'suchit', 'siddharth', 'nikitha', 'mrunmayi', 'preetam',
    'shubham', 'faiza', 'harsh', 'pm',
    # More people discovered
    'ujala', 'mani', 'rittik', 'gopal', 'yatin', 'michelle',
    'john', 'nobal',
}


def slugify(text: str) -> str:
    """Convert text to safe filename slug."""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')[:60]


def get_canonical_person(folder_name: str) -> Optional[str]:
    """Get canonical person name from folder name."""
    name = folder_name.lower()
    
    # Check explicit aliases
    if name in PERSON_ALIASES:
        return PERSON_ALIASES[name]
    
    # Check if it's a known person directly
    if name in KNOWN_PEOPLE:
        return name
    
    # Try to extract person name from folder name patterns
    # e.g., "anshul-dx" -> check if "anshul" is known
    parts = name.split('-')
    if parts[0] in KNOWN_PEOPLE:
        return parts[0]
    
    return None


def parse_daily_note(content: str) -> List[Dict]:
    """Parse a daily note file and extract individual meetings."""
    meetings = []
    current_meeting = None
    current_lines = []
    
    lines = content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # New meeting header: ## Title
        if line.startswith('## ') and not line.startswith('## #'):
            # Save previous meeting
            if current_meeting:
                current_meeting['content'] = '\n'.join(current_lines)
                meetings.append(current_meeting)
            
            title = line[3:].strip()
            current_meeting = {'title': title, 'metadata': {}}
            current_lines = [line]
            i += 1
            
            # Parse metadata lines
            while i < len(lines) and lines[i].startswith('**'):
                meta_line = lines[i]
                current_lines.append(meta_line)
                
                # Extract metadata
                if meta_line.startswith('**Granola ID:**'):
                    current_meeting['metadata']['granola_id'] = meta_line.split(':**')[1].strip()
                elif meta_line.startswith('**Attendees:**'):
                    current_meeting['metadata']['attendees'] = meta_line.split(':**')[1].strip()
                elif meta_line.startswith('**Created:**'):
                    current_meeting['metadata']['created'] = meta_line.split(':**')[1].strip()
                
                i += 1
            continue
        
        if current_meeting:
            current_lines.append(line)
        
        i += 1
    
    # Save last meeting
    if current_meeting:
        current_meeting['content'] = '\n'.join(current_lines)
        meetings.append(current_meeting)
    
    return meetings


def extract_people_from_title(title: str) -> List[str]:
    """Extract person names from meeting title."""
    people = []
    title_lower = title.lower()
    
    # Remove common suffixes
    title_clean = re.sub(r'\s*[-/]\s*(weekly|11|1:1|sync|catch-?up).*$', '', title_lower, flags=re.IGNORECASE)
    
    # Split by common separators
    parts = re.split(r'\s*[/<>|]+\s*', title_clean)
    
    for part in parts:
        part = part.strip()
        # Skip "arnab" (that's the user)
        if 'arnab' in part.lower():
            continue
        
        # Check if this matches a known person
        part_slug = slugify(part)
        canonical = get_canonical_person(part_slug)
        if canonical:
            people.append(canonical)
        else:
            # Try first word
            first_word = part.split()[0] if part.split() else ''
            if first_word.lower() in KNOWN_PEOPLE:
                people.append(first_word.lower())
    
    return list(set(people))


def find_empty_folders(base_path: Path) -> List[Path]:
    """Find empty folders."""
    empty = []
    for folder in base_path.iterdir():
        if folder.is_dir() and not any(folder.iterdir()):
            empty.append(folder)
    return empty


def analyze_people_folders() -> Dict:
    """Analyze current people folder structure."""
    analysis = {
        'canonical_people': defaultdict(list),  # canonical -> [folder_paths]
        'non_people': [],  # folders that aren't people
        'unknown': [],  # can't determine
        'empty': [],  # empty folders
    }
    
    for folder in PEOPLE_PATH.iterdir():
        if not folder.is_dir():
            continue
        
        folder_name = folder.name
        
        # Check if empty
        if not any(folder.iterdir()):
            analysis['empty'].append(folder)
            continue
        
        # Check if it's a non-person folder
        if folder_name.lower() in NON_PERSON_FOLDERS:
            analysis['non_people'].append({
                'folder': folder,
                'destination': NON_PERSON_FOLDERS[folder_name.lower()]
            })
            continue
        
        # Try to get canonical person
        canonical = get_canonical_person(folder_name)
        if canonical:
            analysis['canonical_people'][canonical].append(folder)
        else:
            analysis['unknown'].append(folder)
    
    return analysis


def analyze_daily_notes() -> Dict:
    """Analyze daily notes and extract meetings."""
    analysis = {
        'by_date': {},  # date -> [meetings]
        'by_person': defaultdict(list),  # person -> [meetings with date]
    }
    
    for note_file in sorted(DAILY_NOTES_PATH.glob('*.md')):
        date = note_file.stem  # e.g., "2026-02-11"
        content = note_file.read_text()
        meetings = parse_daily_note(content)
        
        analysis['by_date'][date] = meetings
        
        for meeting in meetings:
            people = extract_people_from_title(meeting['title'])
            for person in people:
                analysis['by_person'][person].append({
                    'date': date,
                    'meeting': meeting,
                    'source_file': note_file
                })
    
    return analysis


def print_analysis(people_analysis: Dict, daily_analysis: Dict):
    """Print analysis summary."""
    print("=" * 60)
    print("PEOPLE FOLDER ANALYSIS")
    print("=" * 60)
    
    print(f"\n📁 Empty folders to delete: {len(people_analysis['empty'])}")
    for folder in people_analysis['empty'][:10]:
        print(f"   - {folder.name}")
    if len(people_analysis['empty']) > 10:
        print(f"   ... and {len(people_analysis['empty']) - 10} more")
    
    print(f"\n🚫 Non-person folders to relocate: {len(people_analysis['non_people'])}")
    for item in people_analysis['non_people']:
        dest = '/'.join(item['destination'])
        print(f"   - {item['folder'].name} → {dest}/")
    
    print(f"\n👥 People with multiple folders (need consolidation):")
    for person, folders in people_analysis['canonical_people'].items():
        if len(folders) > 1:
            print(f"   - {person}: {[f.name for f in folders]}")
    
    print(f"\n❓ Unknown folders: {len(people_analysis['unknown'])}")
    for folder in people_analysis['unknown'][:15]:
        print(f"   - {folder.name}")
    if len(people_analysis['unknown']) > 15:
        print(f"   ... and {len(people_analysis['unknown']) - 15} more")
    
    print("\n" + "=" * 60)
    print("DAILY NOTES ANALYSIS")
    print("=" * 60)
    
    print(f"\n📅 Total daily note files: {len(daily_analysis['by_date'])}")
    print(f"👥 People mentioned in daily notes: {len(daily_analysis['by_person'])}")
    
    # Show people with meetings in daily notes
    print(f"\n📊 Top people by meeting count in daily notes:")
    sorted_people = sorted(daily_analysis['by_person'].items(), key=lambda x: len(x[1]), reverse=True)
    for person, meetings in sorted_people[:15]:
        print(f"   - {person}: {len(meetings)} meetings")


def consolidate_person_folders(canonical: str, folders: List[Path], dry_run: bool = True) -> List[str]:
    """Consolidate multiple folders for same person into one."""
    actions = []
    
    if len(folders) <= 1:
        return actions
    
    # Target folder is the canonical name
    target_folder = PEOPLE_PATH / canonical
    
    for folder in folders:
        if folder.name == canonical:
            continue  # Skip the target folder itself
        
        # Move all files from this folder to target
        for file in folder.glob('*'):
            if file.is_file():
                target_file = target_folder / file.name
                action = f"MOVE: {file} → {target_file}"
                actions.append(action)
                
                if not dry_run:
                    target_folder.mkdir(parents=True, exist_ok=True)
                    if not target_file.exists():
                        shutil.move(str(file), str(target_file))
                    else:
                        # Handle conflict - append suffix
                        stem = target_file.stem
                        suffix = target_file.suffix
                        new_name = f"{stem}-from-{folder.name}{suffix}"
                        shutil.move(str(file), str(target_folder / new_name))
        
        # Remove empty folder
        if not dry_run and not any(folder.iterdir()):
            folder.rmdir()
            actions.append(f"DELETE FOLDER: {folder}")
    
    return actions


def relocate_non_person_folders(non_people: List[Dict], dry_run: bool = True) -> List[str]:
    """Move non-person folders from people/ to their proper location."""
    actions = []
    
    for item in non_people:
        source_folder = item['folder']
        dest_parts = item['destination']  # e.g., ('projects', 'itau')
        
        # Build destination path
        target_folder = VAULT_PATH / dest_parts[0] / dest_parts[1]
        
        action = f"RELOCATE: people/{source_folder.name}/ → {'/'.join(dest_parts)}/"
        actions.append(action)
        
        if not dry_run:
            target_folder.mkdir(parents=True, exist_ok=True)
            
            # Move all files
            for file in source_folder.glob('*'):
                if file.is_file():
                    target_file = target_folder / file.name
                    if not target_file.exists():
                        shutil.move(str(file), str(target_file))
                    else:
                        # Handle conflict
                        stem = target_file.stem
                        suffix = target_file.suffix
                        new_name = f"{stem}-dup{suffix}"
                        shutil.move(str(file), str(target_folder / new_name))
            
            # Remove empty source folder
            if not any(source_folder.iterdir()):
                source_folder.rmdir()
    
    return actions


def sync_daily_to_people(daily_analysis: Dict, dry_run: bool = True) -> List[str]:
    """Copy meeting summaries from daily notes to people folders."""
    actions = []
    
    for person, meetings in daily_analysis['by_person'].items():
        person_folder = PEOPLE_PATH / person
        
        for item in meetings:
            date = item['date']
            meeting = item['meeting']
            
            # Check if this meeting already exists in person folder
            existing_files = list(person_folder.glob(f"{date}*.md")) if person_folder.exists() else []
            
            # Create summary file name
            title_slug = slugify(meeting['title'])[:40]
            summary_file = person_folder / f"{date}-summary-{title_slug}.md"
            
            # Check if we already have this granola_id
            granola_id = meeting['metadata'].get('granola_id', '')
            already_exists = False
            
            for ef in existing_files:
                if granola_id and granola_id in ef.read_text():
                    already_exists = True
                    break
            
            if not already_exists:
                action = f"CREATE SUMMARY: {summary_file.relative_to(VAULT_PATH)}"
                actions.append(action)
                
                if not dry_run:
                    person_folder.mkdir(parents=True, exist_ok=True)
                    
                    # Build the summary content
                    content_lines = [
                        "---",
                        f'title: "{meeting["title"]}"',
                        f'date: "{date}"',
                        f'type: "summary"',
                        f'granola_id: "{granola_id}"',
                    ]
                    if meeting['metadata'].get('attendees'):
                        content_lines.append(f'attendees: "{meeting["metadata"]["attendees"]}"')
                    content_lines.append("---\n")
                    content_lines.append(meeting['content'])
                    
                    summary_file.write_text('\n'.join(content_lines))
    
    return actions


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Reorganize vault structure')
    parser.add_argument('--dry-run', action='store_true', default=True, help='Preview changes without applying')
    parser.add_argument('--apply', action='store_true', help='Actually apply changes')
    parser.add_argument('--analyze-only', action='store_true', help='Only show analysis, no actions')
    args = parser.parse_args()
    
    dry_run = not args.apply
    
    print("🔍 Analyzing vault structure...\n")
    
    people_analysis = analyze_people_folders()
    daily_analysis = analyze_daily_notes()
    
    print_analysis(people_analysis, daily_analysis)
    
    if args.analyze_only:
        return
    
    print("\n" + "=" * 60)
    print("PLANNED ACTIONS" + (" (DRY RUN)" if dry_run else " (APPLYING)"))
    print("=" * 60)
    
    all_actions = []
    
    # 1. Delete empty folders
    print("\n📁 Empty folder cleanup:")
    for folder in people_analysis['empty']:
        action = f"DELETE EMPTY: {folder.name}"
        all_actions.append(action)
        print(f"   {action}")
        if not dry_run:
            folder.rmdir()
    
    # 2. Relocate non-person folders
    print("\n🚚 Relocating non-person folders:")
    actions = relocate_non_person_folders(people_analysis['non_people'], dry_run)
    all_actions.extend(actions)
    for action in actions:
        print(f"   {action}")
    
    # 3. Consolidate duplicate person folders
    print("\n👥 Person folder consolidation:")
    for person, folders in people_analysis['canonical_people'].items():
        if len(folders) > 1:
            actions = consolidate_person_folders(person, folders, dry_run)
            all_actions.extend(actions)
            for action in actions:
                print(f"   {action}")
    
    # 4. Sync daily summaries to people folders
    print("\n📝 Daily summary sync to people folders:")
    actions = sync_daily_to_people(daily_analysis, dry_run)
    all_actions.extend(actions)
    for action in actions[:20]:
        print(f"   {action}")
    if len(actions) > 20:
        print(f"   ... and {len(actions) - 20} more")
    
    print(f"\n{'=' * 60}")
    print(f"Total actions: {len(all_actions)}")
    if dry_run:
        print("Run with --apply to execute these changes")


if __name__ == '__main__':
    main()
