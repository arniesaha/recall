"""
Recall API
Main FastAPI application
"""

import os
import logging
import asyncio
import uuid
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Security, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime
import httpx

from indexer import Indexer
from vectorless import VectorlessSearcher
from config import settings

# Prometheus metrics
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter, Histogram, Gauge, Info

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Security
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    if credentials.credentials != settings.api_token:
        raise HTTPException(status_code=401, detail="Invalid token")
    return credentials.credentials


# ============== Job State Management ==============

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

# In-memory job storage (jobs don't survive restart, which is fine)
jobs: Dict[str, Dict[str, Any]] = {}


# Global instances
indexer: Indexer = None
fts_index = None

# ============== Custom Prometheus Metrics ==============

# Search metrics by mode
SEARCH_LATENCY = Histogram(
    'recall_search_latency_seconds',
    'Search latency in seconds',
    ['mode', 'vault'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

SEARCH_RESULTS = Histogram(
    'recall_search_results_count',
    'Number of search results returned',
    ['mode'],
    buckets=[0, 1, 5, 10, 20, 50, 100]
)

# RAG query metrics
RAG_LATENCY = Histogram(
    'recall_rag_query_latency_seconds',
    'RAG query latency in seconds',
    ['vault'],
    buckets=[1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 60.0]
)

# (Ollama metrics removed — vectorless mode)

# Index metrics
INDEX_DURATION = Histogram(
    'recall_index_duration_seconds',
    'Indexing job duration in seconds',
    ['vault', 'full'],
    buckets=[10, 30, 60, 120, 300, 600, 1800]
)

INDEX_DOCUMENTS = Gauge(
    'recall_indexed_documents',
    'Number of indexed documents',
    ['vault', 'index_type']  # vector, fts
)

# Indexing progress (for active jobs)
INDEX_JOB_RUNNING = Gauge(
    'recall_index_job_running',
    'Whether an indexing job is currently running (1=yes, 0=no)'
)

INDEX_TOTAL_FILES = Gauge(
    'recall_index_total_files',
    'Total files to index in current job'
)

INDEX_PROCESSED_FILES = Gauge(
    'recall_index_processed_files',
    'Files processed so far in current job'
)

INDEX_PROGRESS_PERCENT = Gauge(
    'recall_index_progress_percent',
    'Current indexing job progress (0-100)'
)

INDEX_ETA_SECONDS = Gauge(
    'recall_index_eta_seconds',
    'Estimated time remaining for current index job'
)

# Component health
COMPONENT_UP = Gauge(
    'recall_component_up',
    'Component health status (1=up, 0=down)',
    ['component']  # ollama, lancedb, fts
)

# API info
API_INFO = Info('recall_api', 'API version and build info')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup."""
    global indexer, fts_index
    
    logger.info("Starting Recall API (vectorless mode)...")
    
    # Initialize FTS index
    from fts_index import FTSIndex
    fts_db_path = settings.fts_db_path
    try:
        fts_index = FTSIndex(fts_db_path)
        logger.info(f"FTS index initialized at {fts_index.db_path}")
    except Exception as e:
        logger.error(f"FTS index failed: {e}")
        fts_index = None
    
    # Initialize indexer (FTS-only)
    indexer = Indexer(settings, fts_index=fts_index)
    
    # Initialize metrics
    COMPONENT_UP.labels(component="fts").set(1 if fts_index else 0)
    INDEX_DOCUMENTS.labels(vault="work", index_type="fts").set(0)
    INDEX_DOCUMENTS.labels(vault="personal", index_type="fts").set(0)
    
    logger.info("Recall API ready (BM25 + Gemini Flash)")
    
    yield
    
    logger.info("Shutting down Recall API...")
    if fts_index:
        fts_index.close()


app = FastAPI(
    title="Recall API",
    description="Personal knowledge system with intelligent search",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative dev
        "https://recall.arnabsaha.com",
        "https://recallapi.arnabsaha.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instrument with Prometheus
instrumentator = Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_respect_env_var=False,  # Don't check env var
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/metrics", "/ping"],
    inprogress_name="recall_inprogress_requests",
    inprogress_labels=True,
)
instrumentator.instrument(app)

# Set API info
API_INFO.info({
    'version': '1.0.0',
    'environment': os.getenv('ENVIRONMENT', 'production'),
})

# Add metrics endpoint manually using prometheus_client
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

async def update_health_metrics():
    """Update component health and document count metrics."""
    global fts_index
    COMPONENT_UP.labels(component="fts").set(1 if fts_index else 0)
    try:
        if fts_index:
            INDEX_DOCUMENTS.labels(vault="work", index_type="fts").set(fts_index.get_document_count("work"))
            INDEX_DOCUMENTS.labels(vault="personal", index_type="fts").set(fts_index.get_document_count("personal"))
    except:
        pass


@app.get("/metrics", tags=["monitoring"], include_in_schema=True)
async def metrics():
    """Prometheus metrics endpoint."""
    # Update health metrics on each scrape
    await update_health_metrics()
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


# ============== Models ==============

class SearchRequest(BaseModel):
    query: str
    vault: Optional[str] = "all"  # "work", "personal", "all"
    category: Optional[str] = None
    person: Optional[str] = None
    limit: int = 10
    mode: Optional[str] = "hybrid"  # "vector", "bm25", "hybrid", "query"
    date_from: Optional[str] = None  # YYYY-MM-DD format (auto-parsed from query if not set)
    date_to: Optional[str] = None    # YYYY-MM-DD format (auto-parsed from query if not set)


class SearchResult(BaseModel):
    score: float
    file_path: str
    title: str
    excerpt: str
    date: Optional[str]
    people: List[str]
    category: str
    vault: str


class SearchResponse(BaseModel):
    results: List[SearchResult]
    total: int
    query_time_ms: int


class QueryRequest(BaseModel):
    question: str
    vault: Optional[str] = "all"
    mode: Optional[str] = None  # None=hybrid, "vectorless", "fullcontext"


class QueryResponse(BaseModel):
    answer: str
    sources: List[dict]
    query_time_ms: int


class PrepResponse(BaseModel):
    person: str
    meeting_count: int
    last_meeting: Optional[str]
    recent_topics: List[str]
    open_actions: List[str]
    recent_meetings: List[dict]


class IndexRequest(BaseModel):
    vault: Optional[str] = "all"
    full: bool = False


class IndexResponse(BaseModel):
    status: str
    indexed: int
    duration_ms: int


class AsyncIndexRequest(BaseModel):
    vault: Optional[str] = "all"
    full: bool = False
    rebuild: bool = False  # Alias for full - triggers full reindex with schema refresh
    callback_url: Optional[str] = None
    use_gpu: bool = True  # Wake GPU PC for faster embeddings (default: True)


class AsyncIndexStartResponse(BaseModel):
    job_id: str
    status: str


class IndexProgressInfo(BaseModel):
    """Progress info for a running indexing job."""
    processed: int = 0
    total: int = 0
    percent: float = 0.0
    current_file: Optional[str] = None
    eta_seconds: Optional[float] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None
    indexed: Optional[int] = None
    error: Optional[str] = None
    progress: Optional[IndexProgressInfo] = None


class HealthResponse(BaseModel):
    status: str
    components: dict
    stats: dict


# ============== Endpoints ==============

@app.get("/debug/token")
async def debug_token():
    """Debug endpoint to check token config."""
    return {
        "configured_token_length": len(settings.api_token),
        "configured_token_preview": settings.api_token[:4] + "..." if len(settings.api_token) > 4 else settings.api_token,
    }


@app.get("/ping")
async def ping():
    """Lightweight liveness check - always responds fast."""
    return {"status": "ok", "time": datetime.now().isoformat()}


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    fts_status = "ok" if fts_index else "unavailable"
    COMPONENT_UP.labels(component="fts").set(1 if fts_index else 0)
    
    stats = {
        "work_fts": 0,
        "personal_fts": 0,
        "active_jobs": len([j for j in jobs.values() if j["status"] in [JobStatus.PENDING, JobStatus.RUNNING]]),
    }
    try:
        if fts_index:
            stats["work_fts"] = fts_index.get_document_count("work")
            stats["personal_fts"] = fts_index.get_document_count("personal")
            INDEX_DOCUMENTS.labels(vault="work", index_type="fts").set(stats["work_fts"])
            INDEX_DOCUMENTS.labels(vault="personal", index_type="fts").set(stats["personal_fts"])
    except:
        pass
    
    return HealthResponse(
        status="healthy" if fts_status == "ok" else "degraded",
        components={"fts": fts_status},
        stats=stats
    )


@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Search across vaults.
    
    Modes:
    - "vector": Pure semantic search (fast)
    - "bm25": Pure keyword search (fast)
    - "hybrid": BM25 + Vector with RRF fusion (recommended)
    - "query": Full pipeline with query expansion + reranking (best quality, slower)
    - "vectorless": BM25-only search, no embeddings needed (fast, no GPU)
    """
    import time
    start = time.time()
    mode = request.mode or "hybrid"
    
    # Route vectorless mode to dedicated searcher
    if mode == "vectorless":
        vs = get_vectorless_searcher()
        results = await vs.search(
            query=request.query,
            vault=request.vault,
            limit=request.limit,
            person=request.person,
            date_from=request.date_from,
            date_to=request.date_to,
        )
        duration_ms = int((time.time() - start) * 1000)
        SEARCH_LATENCY.labels(mode="vectorless", vault=request.vault or "all").observe(duration_ms / 1000)
        SEARCH_RESULTS.labels(mode="vectorless").observe(len(results))
        return SearchResponse(results=results, total=len(results), query_time_ms=duration_ms)
    
    # All search modes now route through vectorless searcher
    vs = get_vectorless_searcher()
    results = await vs.search(
        query=request.query,
        vault=request.vault,
        limit=request.limit,
        person=request.person,
        date_from=request.date_from,
        date_to=request.date_to,
    )
    
    duration = time.time() - start
    duration_ms = int(duration * 1000)
    
    # Record metrics
    SEARCH_LATENCY.labels(mode=mode, vault=request.vault or "all").observe(duration)
    SEARCH_RESULTS.labels(mode=mode).observe(len(results))
    
    return SearchResponse(
        results=results,
        total=len(results),
        query_time_ms=duration_ms
    )


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """RAG query with LLM-generated answer.
    
    Set mode field to "vectorless" or "fullcontext" for vectorless RAG.
    Default uses hybrid (BM25 + vector) search."""
    global searcher
    
    import time
    start = time.time()
    
    # Check if vectorless mode requested
    mode = getattr(request, "mode", None) or "hybrid"
    
    if mode in ("vectorless", "fullcontext"):
        vs = get_vectorless_searcher()
        answer, sources, metadata = await vs.query_with_llm(
            question=request.question,
            vault=request.vault,
            mode=mode,
        )
        duration_ms = int((time.time() - start) * 1000)
        RAG_LATENCY.labels(vault=request.vault or "all").observe(duration_ms / 1000)
        return QueryResponse(answer=answer, sources=sources, query_time_ms=duration_ms)
    
    vs = get_vectorless_searcher()
    answer, sources, _ = await vs.query_with_llm(
        question=request.question,
        vault=request.vault,
        mode="vectorless",
    )
    
    duration = time.time() - start
    duration_ms = int(duration * 1000)
    
    # Record metrics
    RAG_LATENCY.labels(vault=request.vault or "all").observe(duration)
    
    return QueryResponse(
        answer=answer,
        sources=sources,
        query_time_ms=duration_ms
    )


@app.get("/prep/{person}", response_model=PrepResponse)
async def prep_for_meeting(person: str):
    """Get context for 1:1 with a person."""
    global searcher
    
    context = await searcher.get_person_context(person)
    
    return PrepResponse(**context)


@app.get("/actions")
async def get_actions(person: Optional[str] = None, limit: int = 20):
    """Get open action items."""
    global searcher
    
    actions = await searcher.get_action_items(person=person, limit=limit)
    return {"actions": actions}


@app.post("/index", response_model=IndexResponse)
async def run_indexing(request: IndexRequest):
    """Trigger indexing of vault content (synchronous)."""
    global indexer
    
    start = time.time()
    
    if request.full:
        indexed = await indexer.full_reindex(vault=request.vault)
    else:
        indexed = await indexer.incremental_index(vault=request.vault)
    
    duration_ms = int((time.time() - start) * 1000)
    
    return IndexResponse(
        status="complete",
        indexed=indexed,
        duration_ms=duration_ms
    )


async def _run_indexing_job(job_id: str, full: bool, vault: str, callback_url: Optional[str], use_gpu: bool = False):
    """Background task to run FTS indexing."""
    global indexer, jobs
    
    jobs[job_id]["status"] = JobStatus.RUNNING
    start = time.time()
    
    INDEX_JOB_RUNNING.set(1)
    INDEX_TOTAL_FILES.set(0)
    INDEX_PROCESSED_FILES.set(0)
    INDEX_PROGRESS_PERCENT.set(0)
    INDEX_ETA_SECONDS.set(0)
    
    async def progress_callback(processed: int, total: int, current_file: str):
        INDEX_TOTAL_FILES.set(total)
        INDEX_PROCESSED_FILES.set(processed)
        if total > 0:
            percent = (processed / total) * 100
            INDEX_PROGRESS_PERCENT.set(percent)
            elapsed = time.time() - start
            if processed > 0:
                rate = processed / elapsed
                remaining = total - processed
                eta = remaining / rate if rate > 0 else 0
                INDEX_ETA_SECONDS.set(eta)
        jobs[job_id]["progress"] = {
            "processed": processed,
            "total": total,
            "percent": round((processed / total) * 100, 1) if total > 0 else 0,
            "current_file": current_file,
        }
    
    try:
        if full:
            indexed = await indexer.full_reindex(vault=vault, progress_callback=progress_callback)
        else:
            indexed = await indexer.incremental_index(vault=vault, progress_callback=progress_callback)
        
        duration_ms = int((time.time() - start) * 1000)
        
        jobs[job_id].update({
            "status": JobStatus.COMPLETED,
            "completed_at": time.time(),
            "duration_ms": duration_ms,
            "indexed": indexed,
        })
        
        INDEX_JOB_RUNNING.set(0)
        INDEX_PROGRESS_PERCENT.set(100)
        INDEX_ETA_SECONDS.set(0)
        
        if callback_url:
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(callback_url, json={
                        "job_id": job_id, "status": "completed",
                        "stats": {"indexed": indexed, "duration_ms": duration_ms},
                    }, timeout=30.0)
            except Exception as e:
                logger.error(f"Callback failed: {e}")
    
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        jobs[job_id].update({
            "status": JobStatus.FAILED,
            "completed_at": time.time(),
            "duration_ms": duration_ms,
            "error": str(e),
        })
        logger.error(f"Job {job_id} failed: {e}")
        INDEX_JOB_RUNNING.set(0)
        INDEX_ETA_SECONDS.set(0)


@app.post("/index/start", response_model=AsyncIndexStartResponse)
async def start_indexing(request: AsyncIndexRequest, background_tasks: BackgroundTasks):
    """Start async indexing job. Returns immediately with job_id."""
    global jobs
    
    job_id = str(uuid.uuid4())
    
    # rebuild is an alias for full - either triggers full reindex
    do_full = request.full or request.rebuild
    
    jobs[job_id] = {
        "status": JobStatus.PENDING,
        "started_at": time.time(),
        "completed_at": None,
        "duration_ms": None,
        "indexed": None,
        "error": None,
        "vault": request.vault,
        "full": do_full,
        "callback_url": request.callback_url,
    }
    
    # Schedule background task
    background_tasks.add_task(
        _run_indexing_job,
        job_id=job_id,
        full=do_full,
        vault=request.vault,
        callback_url=request.callback_url,
        use_gpu=request.use_gpu
    )
    
    logger.info(f"Started indexing job {job_id} (vault={request.vault}, full={do_full}, use_gpu={request.use_gpu})")
    
    return AsyncIndexStartResponse(
        job_id=job_id,
        status="started"
    )


@app.get("/index/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get status of an indexing job."""
    global jobs
    
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    
    # Get progress info if available
    progress = None
    if "progress" in job and job["progress"]:
        p = job["progress"]
        # Calculate ETA
        elapsed = time.time() - job["started_at"] if job["started_at"] else 0
        eta = None
        if p.get("processed", 0) > 0 and p.get("total", 0) > p.get("processed", 0):
            rate = p["processed"] / elapsed if elapsed > 0 else 0
            remaining = p["total"] - p["processed"]
            eta = remaining / rate if rate > 0 else None
        
        progress = IndexProgressInfo(
            processed=p.get("processed", 0),
            total=p.get("total", 0),
            percent=p.get("percent", 0.0),
            current_file=p.get("current_file"),
            eta_seconds=eta,
        )
    
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"].value,
        started_at=datetime.fromtimestamp(job["started_at"]).isoformat() if job["started_at"] else None,
        completed_at=datetime.fromtimestamp(job["completed_at"]).isoformat() if job["completed_at"] else None,
        duration_ms=job["duration_ms"],
        indexed=job["indexed"],
        error=job.get("error"),
        progress=progress,
    )


@app.post("/index/cancel/{job_id}")
async def cancel_job(job_id: str):
    """Request cancellation of a running indexing job."""
    global jobs, indexer
    
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    
    if job["status"] not in [JobStatus.PENDING, JobStatus.RUNNING]:
        return {"status": "already_finished", "job_status": job["status"].value}
    
    # Request cancellation
    indexer.request_cancel()
    
    return {"status": "cancel_requested", "job_id": job_id}


@app.get("/index/jobs")
async def list_jobs(limit: int = 10):
    """List recent indexing jobs."""
    global jobs
    
    sorted_jobs = sorted(
        jobs.items(),
        key=lambda x: x[1]["started_at"] or 0,
        reverse=True
    )[:limit]
    
    return {
        "jobs": [
            {
                "job_id": job_id,
                "status": job["status"].value,
                "vault": job.get("vault"),
                "full": job.get("full"),
                "started_at": datetime.fromtimestamp(job["started_at"]).isoformat() if job["started_at"] else None,
                "indexed": job.get("indexed"),
            }
            for job_id, job in sorted_jobs
        ]
    }


@app.get("/index/progress")
async def get_index_progress():
    """Get current indexing progress (for the most recent running job).
    
    Returns a simple progress summary for easy monitoring.
    """
    global jobs
    
    # Find the most recent running job
    running_jobs = [
        (job_id, job) for job_id, job in jobs.items()
        if job["status"] == JobStatus.RUNNING
    ]
    
    if not running_jobs:
        # Check for most recent completed job
        completed_jobs = [
            (job_id, job) for job_id, job in jobs.items()
            if job["status"] in [JobStatus.COMPLETED, JobStatus.FAILED]
        ]
        if completed_jobs:
            latest = max(completed_jobs, key=lambda x: x[1].get("completed_at", 0))
            job_id, job = latest
            return {
                "status": "idle",
                "last_job": {
                    "job_id": job_id,
                    "status": job["status"].value,
                    "indexed": job.get("indexed"),
                    "completed_at": datetime.fromtimestamp(job["completed_at"]).isoformat() if job.get("completed_at") else None,
                }
            }
        return {"status": "idle", "last_job": None}
    
    # Get progress from the running job
    job_id, job = running_jobs[0]
    progress = job.get("progress", {})
    
    processed = progress.get("processed", 0)
    total = progress.get("total", 0)
    percent = progress.get("percent", 0.0)
    
    # Calculate ETA
    elapsed = time.time() - job["started_at"] if job["started_at"] else 0
    eta_seconds = None
    eta_human = None
    if processed > 0 and total > processed:
        rate = processed / elapsed if elapsed > 0 else 0
        remaining = total - processed
        eta_seconds = remaining / rate if rate > 0 else 0
        
        # Human-readable ETA
        if eta_seconds:
            if eta_seconds < 60:
                eta_human = f"{int(eta_seconds)}s"
            elif eta_seconds < 3600:
                eta_human = f"{int(eta_seconds / 60)}m {int(eta_seconds % 60)}s"
            else:
                eta_human = f"{int(eta_seconds / 3600)}h {int((eta_seconds % 3600) / 60)}m"
    
    return {
        "status": "running",
        "job_id": job_id,
        "processed": processed,
        "total": total,
        "percent": round(percent, 1),
        "eta_seconds": round(eta_seconds, 0) if eta_seconds else None,
        "eta_human": eta_human,
        "elapsed_seconds": round(elapsed, 0),
        "current_file": progress.get("current_file"),
    }


# /index/init removed (no LanceDB tables to init)


@app.get("/stats")
async def get_stats():
    """Get indexing statistics."""
    stats = {"work_fts": 0, "personal_fts": 0}
    try:
        if fts_index:
            stats["work_fts"] = fts_index.get_document_count("work")
            stats["personal_fts"] = fts_index.get_document_count("personal")
    except:
        pass
    return stats


# ============== Note Access Endpoints ==============

class NoteResponse(BaseModel):
    path: str
    title: str
    content: str
    vault: str
    modified: Optional[str] = None
    source_type: str = "markdown"  # markdown or pdf
    page_number: Optional[int] = None


class NoteTreeResponse(BaseModel):
    tree: Dict[str, Any]
    total_files: int


@app.get("/notes/tree", response_model=NoteTreeResponse)
async def get_notes_tree():
    """Get the file tree structure for browsing."""
    import os
    from pathlib import Path
    
    def build_tree(base_path: Path, relative_to: Path) -> dict:
        tree = {}
        if not base_path.exists():
            return tree
        
        for item in sorted(base_path.iterdir()):
            if item.name.startswith('.'):
                continue
            
            rel_path = item.relative_to(relative_to)
            
            if item.is_dir():
                subtree = build_tree(item, relative_to)
                if subtree:  # Only include non-empty directories
                    tree[item.name] = subtree
            elif item.suffix in ['.md', '.pdf']:
                if '_files_' not in tree:
                    tree['_files_'] = []
                tree['_files_'].append({
                    'name': item.name,
                    'path': str(rel_path),
                    'type': 'pdf' if item.suffix == '.pdf' else 'markdown'
                })
        
        return tree
    
    result = {}
    total = 0
    
    # Build tree for each vault using separate path settings
    vault_paths = {
        'work': Path(settings.vault_work_path),
        'personal': Path(settings.vault_personal_path)
    }
    
    for vault, vault_path in vault_paths.items():
        if vault_path.exists():
            result[vault] = build_tree(vault_path, vault_path.parent)
            # Count files
            for root, dirs, files in os.walk(vault_path):
                total += len([f for f in files if f.endswith('.md') or f.endswith('.pdf')])
    
    # Also check PDFs directory
    pdf_path = Path(settings.pdf_work_path).parent
    if pdf_path.exists():
        result['pdfs'] = build_tree(pdf_path, pdf_path.parent)
    
    return NoteTreeResponse(tree=result, total_files=total)


@app.get("/notes/recent")
async def get_recent_notes(limit: int = 10):
    """Get recently modified notes."""
    import os
    from pathlib import Path
    
    notes = []
    
    vault_paths = {
        'work': Path(settings.vault_work_path),
        'personal': Path(settings.vault_personal_path)
    }
    
    for vault, vault_path in vault_paths.items():
        if not vault_path.exists():
            continue
        
        for root, dirs, files in os.walk(vault_path):
            for file in files:
                if not file.endswith('.md'):
                    continue
                if file.startswith('.'):
                    continue
                
                full_path = Path(root) / file
                rel_path = full_path.relative_to(vault_path.parent)
                mtime = os.path.getmtime(full_path)
                
                notes.append({
                    'path': str(rel_path),
                    'title': file.replace('.md', ''),
                    'vault': vault,
                    'modified': datetime.fromtimestamp(mtime).isoformat(),
                    'mtime': mtime
                })
    
    # Sort by modification time, most recent first
    notes.sort(key=lambda x: x['mtime'], reverse=True)
    
    # Remove mtime from response and limit
    for note in notes:
        del note['mtime']
    
    return {"notes": notes[:limit]}


@app.get("/notes/tags")
async def get_all_tags(vault: Optional[str] = "all", limit: int = 50):
    """Get all unique tags from notes, sorted by frequency."""
    import os
    import re
    from pathlib import Path
    from collections import Counter
    
    tag_counts = Counter()
    tag_pattern = re.compile(r'#([a-zA-Z][a-zA-Z0-9_\-]*)')
    
    vault_paths = {}
    if vault in ["all", "work"]:
        vault_paths['work'] = Path(settings.vault_work_path)
    if vault in ["all", "personal"]:
        vault_paths['personal'] = Path(settings.vault_personal_path)
    
    for v_name, vault_path in vault_paths.items():
        if not vault_path.exists():
            continue
        
        for root, dirs, files in os.walk(vault_path):
            for file in files:
                if not file.endswith('.md'):
                    continue
                if file.startswith('.'):
                    continue
                
                full_path = Path(root) / file
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Find all tags in content
                    tags = tag_pattern.findall(content)
                    for tag in tags:
                        tag_counts[tag.lower()] += 1
                except Exception:
                    continue
    
    # Sort by count descending, then alphabetically
    sorted_tags = sorted(
        tag_counts.items(),
        key=lambda x: (-x[1], x[0])
    )[:limit]
    
    return {
        "tags": [{"name": tag, "count": count} for tag, count in sorted_tags],
        "total": len(tag_counts)
    }


@app.get("/notes/folders")
async def get_folders(vault: str = "work"):
    """Get list of folders for note creation dropdown."""
    import os
    from pathlib import Path
    
    folders = []
    
    if vault == "personal":
        vault_path = Path(settings.vault_personal_path)
    else:
        vault_path = Path(settings.vault_work_path)
    
    if not vault_path.exists():
        return {"folders": []}
    
    for root, dirs, files in os.walk(vault_path):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        rel_path = Path(root).relative_to(vault_path)
        if str(rel_path) != '.':
            folders.append(str(rel_path))
    
    folders.sort()
    return {"folders": folders}


@app.get("/notes/{path:path}", response_model=NoteResponse)
async def get_note(path: str):
    """Get the full content of a note by path."""
    import os
    from pathlib import Path
    
    # Security: prevent path traversal
    if '..' in path or path.startswith('/'):
        raise HTTPException(status_code=400, detail="Invalid path")
    
    # Strip vault prefix if present (UI sends "work/people/..." but API expects "people/...")
    if path.startswith('work/'):
        path = path[5:]  # Remove "work/"
    elif path.startswith('personal/'):
        path = path[9:]  # Remove "personal/"
    
    # Try to find the file in work or personal vault
    full_path = None
    for vault_path in [Path(settings.vault_work_path), Path(settings.vault_personal_path)]:
        test_path = vault_path / path
        if test_path.exists():
            full_path = test_path
            break
        # Try with .md extension
        test_path = vault_path / f"{path}.md"
        if test_path.exists():
            full_path = test_path
            break
    
    if full_path is None:
        raise HTTPException(status_code=404, detail="Note not found")
    
    # Determine vault from path
    vault = "work" if "work" in str(full_path) else "personal"
    
    # Get file modified time
    mtime = os.path.getmtime(full_path)
    modified = datetime.fromtimestamp(mtime).isoformat()
    
    # Read content
    if full_path.suffix == '.pdf':
        # For PDFs, return metadata only (content viewing handled separately)
        return NoteResponse(
            path=path,
            title=full_path.stem,
            content="[PDF content - use search to query]",
            vault=vault,
            modified=modified,
            source_type="pdf"
        )
    else:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract title from first H1 or filename
        title = full_path.stem
        for line in content.split('\n'):
            if line.startswith('# '):
                title = line[2:].strip()
                break
        
        return NoteResponse(
            path=path,
            title=title,
            content=content,
            vault=vault,
            modified=modified,
            source_type="markdown"
        )


class CreateNoteRequest(BaseModel):
    title: str
    content: str
    vault: str = "work"  # "work" or "personal"
    folder: Optional[str] = None  # Optional subfolder path


@app.post("/notes")
async def create_note(request: CreateNoteRequest):
    """Create a new note."""
    from pathlib import Path
    import re
    
    # Security: prevent path traversal in title and folder
    if '..' in request.title or request.title.startswith('/'):
        raise HTTPException(status_code=400, detail="Invalid title")
    if request.folder and ('..' in request.folder or request.folder.startswith('/')):
        raise HTTPException(status_code=400, detail="Invalid folder path")
    
    # Sanitize title for filename
    safe_title = re.sub(r'[^\w\s\-]', '', request.title).strip()
    safe_title = re.sub(r'\s+', '-', safe_title).lower()
    if not safe_title:
        safe_title = f"note-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    # Determine vault path
    if request.vault == "personal":
        vault_path = Path(settings.vault_personal_path)
    else:
        vault_path = Path(settings.vault_work_path)
    
    # Build full path
    if request.folder:
        target_dir = vault_path / request.folder
    else:
        target_dir = vault_path
    
    # Create directory if it doesn't exist
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Create filename with .md extension
    filename = f"{safe_title}.md"
    full_path = target_dir / filename
    
    # Check if file already exists
    counter = 1
    while full_path.exists():
        filename = f"{safe_title}-{counter}.md"
        full_path = target_dir / filename
        counter += 1
    
    # Write content
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(request.content)
    
    # Return relative path from vault
    rel_path = full_path.relative_to(vault_path.parent)
    
    return {
        "status": "created",
        "path": str(rel_path),
        "filename": filename,
        "vault": request.vault
    }


@app.put("/notes/{path:path}")
async def update_note(path: str, content: str = None, body: dict = None):
    """Update a note's content."""
    from pathlib import Path
    
    # Get content from body if not provided directly
    if content is None and body:
        content = body.get('content')
    
    if content is None:
        raise HTTPException(status_code=400, detail="Content required")
    
    # Security: prevent path traversal
    if '..' in path or path.startswith('/'):
        raise HTTPException(status_code=400, detail="Invalid path")
    
    # Find the file in work or personal vault
    full_path = None
    for vault_path in [Path(settings.vault_work_path), Path(settings.vault_personal_path)]:
        test_path = vault_path / path
        if test_path.exists():
            full_path = test_path
            break
        test_path = vault_path / f"{path}.md"
        if test_path.exists():
            full_path = test_path
            break
    
    if full_path is None:
        raise HTTPException(status_code=404, detail="Note not found")
    
    if full_path.suffix == '.pdf':
        raise HTTPException(status_code=400, detail="Cannot edit PDF files")
    
    # Write content
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return {"status": "updated", "path": path}


# ============== PageIndex (Vectorless RAG for PDFs) ==============

class TreeGenerateRequest(BaseModel):
    pdf_path: str
    vault: str = "work"
    force: bool = False  # Regenerate even if tree exists


class TreeSearchRequest(BaseModel):
    query: str
    vault: str = "all"  # "work", "personal", "all"
    limit: int = 5


class TreeSearchResult(BaseModel):
    doc_name: str
    pdf_path: str
    vault: str
    section: str
    summary: str
    pages: str
    start_page: int
    end_page: int
    text: str
    reasoning: str


class TreeSearchResponse(BaseModel):
    query: str
    results: List[TreeSearchResult]
    query_time_ms: int


@app.post("/tree/generate")
async def generate_tree(request: TreeGenerateRequest):
    """
    Generate PageIndex tree structure for a PDF.
    
    This uses LLM reasoning to create a hierarchical table of contents
    that can be searched without embeddings.
    """
    from pathlib import Path
    
    if not settings.pageindex_enabled:
        raise HTTPException(status_code=400, detail="PageIndex is disabled")
    
    pdf_path = Path(request.pdf_path)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    
    from pageindex_tree import get_tree_generator
    generator = get_tree_generator()
    
    # Check if tree already exists
    if generator.tree_exists(str(pdf_path), request.vault) and not request.force:
        existing = generator.load_tree(str(pdf_path), request.vault)
        return {
            "status": "exists",
            "doc_name": existing.get("doc_name", ""),
            "total_pages": existing.get("total_pages", 0),
            "node_count": generator._count_nodes(existing.get("structure", [])),
            "message": "Tree already exists. Use force=true to regenerate."
        }
    
    # Extract PDF pages
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        pages = []
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text("text")
            if text and text.strip():
                pages.append((page_num, text.strip()))
        doc.close()
    except ImportError:
        raise HTTPException(status_code=500, detail="PyMuPDF not installed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF extraction failed: {e}")
    
    if not pages:
        raise HTTPException(status_code=400, detail="PDF has no extractable text")
    
    # Generate tree
    import time
    start = time.time()
    
    tree_data = await generator.generate_tree(
        pages=pages,
        doc_name=pdf_path.name,
        pdf_path=str(pdf_path),
        vault=request.vault
    )
    
    duration_ms = int((time.time() - start) * 1000)
    
    return {
        "status": "generated",
        "doc_name": tree_data.get("doc_name", ""),
        "total_pages": tree_data.get("total_pages", 0),
        "node_count": generator._count_nodes(tree_data.get("structure", [])),
        "duration_ms": duration_ms,
        "structure": tree_data.get("structure", [])
    }


@app.post("/tree/search", response_model=TreeSearchResponse)
async def search_trees(request: TreeSearchRequest):
    """
    Search PDFs using PageIndex tree reasoning.
    
    The LLM reasons over tree structures to find relevant sections
    without using embeddings. Good for structured documents.
    """
    import time
    
    if not settings.pageindex_enabled:
        raise HTTPException(status_code=400, detail="PageIndex is disabled")
    
    from tree_search import get_tree_searcher
    searcher = get_tree_searcher()
    
    start = time.time()
    results = await searcher.search(
        query=request.query,
        vault=request.vault,
        limit=request.limit
    )
    duration_ms = int((time.time() - start) * 1000)
    
    return TreeSearchResponse(
        query=request.query,
        results=[TreeSearchResult(**r) for r in results],
        query_time_ms=duration_ms
    )


@app.get("/tree/list")
async def list_trees(vault: Optional[str] = None):
    """List all generated PageIndex trees."""
    if not settings.pageindex_enabled:
        raise HTTPException(status_code=400, detail="PageIndex is disabled")
    
    from pageindex_tree import get_tree_generator
    generator = get_tree_generator()
    
    trees = generator.list_trees(vault)
    
    return {
        "trees": trees,
        "total": len(trees)
    }


@app.delete("/tree/{vault}/{doc_name}")
async def delete_tree(vault: str, doc_name: str):
    """Delete a tree by vault and document name."""
    if not settings.pageindex_enabled:
        raise HTTPException(status_code=400, detail="PageIndex is disabled")
    
    from pageindex_tree import get_tree_generator
    generator = get_tree_generator()
    
    # Find the tree by doc_name
    trees = generator.list_trees(vault)
    for tree in trees:
        if tree.get("doc_name") == doc_name:
            pdf_path = tree.get("pdf_path", "")
            if generator.delete_tree(pdf_path, vault):
                return {"status": "deleted", "doc_name": doc_name}
    
    raise HTTPException(status_code=404, detail="Tree not found")


@app.get("/tree/health")
async def pageindex_health():
    """Check PageIndex LLM health."""
    if not settings.pageindex_enabled:
        return {"enabled": False}
    
    from pageindex_llm import get_pageindex_llm
    llm = get_pageindex_llm()
    
    health = await llm.health_check()
    
    return {
        "enabled": True,
        "provider": settings.pageindex_llm_provider,
        "llm_status": health,
        "tree_dir": settings.pageindex_tree_dir
    }


@app.post("/tree/generate-all")
async def generate_all_trees(vault: str = "work", background_tasks: BackgroundTasks = None):
    """
    Generate trees for all PDFs in a vault.
    
    This is a long-running operation that runs in the background.
    """
    from pathlib import Path
    
    if not settings.pageindex_enabled:
        raise HTTPException(status_code=400, detail="PageIndex is disabled")
    
    # Get PDF path for vault
    if vault == "work":
        pdf_path = Path(settings.pdf_work_path)
    else:
        pdf_path = Path(settings.pdf_personal_path)
    
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"PDF directory not found: {pdf_path}")
    
    # List PDFs
    pdfs = list(pdf_path.rglob("*.pdf"))
    
    from pageindex_tree import get_tree_generator
    generator = get_tree_generator()
    
    # Check which need generation
    pending = []
    for pdf in pdfs:
        if not generator.tree_exists(str(pdf), vault):
            pending.append(str(pdf))
    
    if not pending:
        return {
            "status": "complete",
            "message": "All trees already generated",
            "total_pdfs": len(pdfs),
            "pending": 0
        }
    
    # For now, return info about what would be generated
    # TODO: Implement background task for batch generation
    return {
        "status": "pending",
        "message": f"Found {len(pending)} PDFs needing tree generation",
        "total_pdfs": len(pdfs),
        "pending": len(pending),
        "pending_files": [Path(p).name for p in pending]
    }


# ============== Vectorless RAG Endpoints ==============

from vectorless import VectorlessSearcher

# Lazy init (needs fts_index from lifespan)
_vectorless_searcher: Optional[VectorlessSearcher] = None

def get_vectorless_searcher() -> VectorlessSearcher:
    global _vectorless_searcher, fts_index
    if _vectorless_searcher is None:
        _vectorless_searcher = VectorlessSearcher(settings, fts_index=fts_index)
    return _vectorless_searcher


class VectorlessSearchRequest(BaseModel):
    query: str
    vault: Optional[str] = "all"
    limit: int = 10
    person: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None


class VectorlessQueryRequest(BaseModel):
    question: str
    vault: Optional[str] = "all"
    mode: Optional[str] = "vectorless"  # "vectorless" or "fullcontext"


class VectorlessQueryResponse(BaseModel):
    answer: str
    sources: List[dict]
    metadata: dict


@app.post("/search/vectorless", response_model=SearchResponse)
async def vectorless_search(request: VectorlessSearchRequest):
    """
    Vectorless search — BM25 keyword retrieval only.
    No embeddings, no GPU, no Ollama needed.
    """
    vs = get_vectorless_searcher()
    
    start = time.time()
    
    results = await vs.search(
        query=request.query,
        vault=request.vault,
        limit=request.limit,
        person=request.person,
        date_from=request.date_from,
        date_to=request.date_to,
    )
    
    duration_ms = int((time.time() - start) * 1000)
    
    SEARCH_LATENCY.labels(mode="vectorless", vault=request.vault or "all").observe(
        (time.time() - start)
    )
    SEARCH_RESULTS.labels(mode="vectorless").observe(len(results))
    
    return SearchResponse(
        results=results,
        total=len(results),
        query_time_ms=duration_ms,
    )


@app.post("/query/vectorless", response_model=VectorlessQueryResponse)
async def vectorless_query(request: VectorlessQueryRequest):
    """
    Vectorless RAG query — BM25 retrieval + long-context LLM answer.
    
    Modes:
      - vectorless: BM25 chunks stuffed into LLM context (default, fast)
      - fullcontext: Full file contents loaded into LLM context (best quality, higher cost)
    
    No embeddings needed. No GPU needed.
    """
    vs = get_vectorless_searcher()
    
    start = time.time()
    
    answer, sources, metadata = await vs.query_with_llm(
        question=request.question,
        vault=request.vault,
        mode=request.mode or "vectorless",
    )
    
    duration = time.time() - start
    RAG_LATENCY.labels(vault=request.vault or "all").observe(duration)
    
    return VectorlessQueryResponse(
        answer=answer,
        sources=sources,
        metadata=metadata,
    )
