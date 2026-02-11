"""
note-rag API
Main FastAPI application
"""

import os
import logging
import asyncio
import uuid
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Security, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime
import lancedb
import httpx

from indexer import Indexer
from searcher import Searcher
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
db: lancedb.DBConnection = None
indexer: Indexer = None
searcher: Searcher = None
fts_index = None

# ============== Custom Prometheus Metrics ==============

# Search metrics by mode
SEARCH_LATENCY = Histogram(
    'noterag_search_latency_seconds',
    'Search latency in seconds',
    ['mode', 'vault'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

SEARCH_RESULTS = Histogram(
    'noterag_search_results_count',
    'Number of search results returned',
    ['mode'],
    buckets=[0, 1, 5, 10, 20, 50, 100]
)

# RAG query metrics
RAG_LATENCY = Histogram(
    'noterag_rag_query_latency_seconds',
    'RAG query latency in seconds',
    ['vault'],
    buckets=[1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 60.0]
)

# Ollama metrics
OLLAMA_LATENCY = Histogram(
    'noterag_ollama_latency_seconds',
    'Ollama embedding/generation latency',
    ['operation'],  # embed, generate
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

OLLAMA_ERRORS = Counter(
    'noterag_ollama_errors_total',
    'Ollama errors',
    ['operation']
)

# Index metrics
INDEX_DURATION = Histogram(
    'noterag_index_duration_seconds',
    'Indexing job duration in seconds',
    ['vault', 'full'],
    buckets=[10, 30, 60, 120, 300, 600, 1800]
)

INDEX_DOCUMENTS = Gauge(
    'noterag_indexed_documents',
    'Number of indexed documents',
    ['vault', 'index_type']  # vector, fts
)

# Component health
COMPONENT_UP = Gauge(
    'noterag_component_up',
    'Component health status (1=up, 0=down)',
    ['component']  # ollama, lancedb, fts
)

# API info
API_INFO = Info('noterag_api', 'API version and build info')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup."""
    global db, indexer, searcher, fts_index
    
    logger.info("Starting note-rag API...")
    
    # Connect to LanceDB
    logger.info(f"Connecting to LanceDB at {settings.lancedb_path}")
    db = lancedb.connect(settings.lancedb_path)
    
    # Initialize FTS index for hybrid search (optional - falls back to vector-only)
    from fts_index import FTSIndex
    import os
    fts_db_path = os.path.join(settings.lancedb_path, "fts_index.db")
    try:
        fts_index = FTSIndex(fts_db_path)
        logger.info(f"FTS index initialized at {fts_index.db_path}")
    except Exception as e:
        logger.warning(f"FTS index unavailable: {e}. Hybrid search will fall back to vector-only.")
        fts_index = None
    
    # Initialize indexer and searcher with FTS index
    indexer = Indexer(db, settings, fts_index=fts_index)
    searcher = Searcher(db, settings, fts_index=fts_index)
    
    # Initialize tables if needed
    await indexer.init_tables()
    
    logger.info("note-rag API ready (hybrid search enabled)")
    
    yield
    
    logger.info("Shutting down note-rag API...")
    if fts_index:
        fts_index.close()


app = FastAPI(
    title="note-rag API",
    description="Personal knowledge system with intelligent search",
    version="1.0.0",
    lifespan=lifespan
)

# Instrument with Prometheus
instrumentator = Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_respect_env_var=False,  # Don't check env var
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/metrics", "/ping"],
    inprogress_name="noterag_inprogress_requests",
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

@app.get("/metrics", tags=["monitoring"], include_in_schema=True)
async def metrics():
    """Prometheus metrics endpoint."""
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
    callback_url: Optional[str] = None


class AsyncIndexStartResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None
    indexed: Optional[int] = None
    error: Optional[str] = None


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
    global db, indexer
    
    # Check Ollama (with short timeout)
    ollama_status = "ok"
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{settings.ollama_url}/api/tags", timeout=3.0)
            if resp.status_code != 200:
                ollama_status = "error"
    except Exception as e:
        ollama_status = f"error: {str(e)}"
    
    # Check LanceDB
    lancedb_status = "ok"
    try:
        tables = db.table_names()
    except Exception as e:
        lancedb_status = f"error: {str(e)}"
    
    # Check FTS
    fts_status = "ok" if fts_index else "unavailable"
    
    # Update Prometheus health gauges
    COMPONENT_UP.labels(component="ollama").set(1 if ollama_status == "ok" else 0)
    COMPONENT_UP.labels(component="lancedb").set(1 if lancedb_status == "ok" else 0)
    COMPONENT_UP.labels(component="fts").set(1 if fts_index else 0)
    
    # Get stats
    stats = {
        "work_vectors": 0,
        "personal_vectors": 0,
        "work_fts": 0,
        "personal_fts": 0,
        "active_jobs": len([j for j in jobs.values() if j["status"] in [JobStatus.PENDING, JobStatus.RUNNING]]),
    }
    try:
        if "work" in db.table_names():
            stats["work_vectors"] = db.open_table("work").count_rows()
        if "personal" in db.table_names():
            stats["personal_vectors"] = db.open_table("personal").count_rows()
        # FTS stats
        if fts_index:
            try:
                stats["work_fts"] = fts_index.get_document_count("work")
                stats["personal_fts"] = fts_index.get_document_count("personal")
            except:
                stats["work_fts"] = 0
                stats["personal_fts"] = 0
        else:
            stats["fts_available"] = False
        
        # Update index document gauges
        INDEX_DOCUMENTS.labels(vault="work", index_type="vector").set(stats["work_vectors"])
        INDEX_DOCUMENTS.labels(vault="personal", index_type="vector").set(stats["personal_vectors"])
        INDEX_DOCUMENTS.labels(vault="work", index_type="fts").set(stats["work_fts"])
        INDEX_DOCUMENTS.labels(vault="personal", index_type="fts").set(stats["personal_fts"])
    except:
        pass
    
    return HealthResponse(
        status="healthy" if ollama_status == "ok" and lancedb_status == "ok" else "degraded",
        components={
            "ollama": ollama_status,
            "lancedb": lancedb_status,
            "fts": fts_status,
        },
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
    """
    global searcher
    
    import time
    start = time.time()
    mode = request.mode or "hybrid"
    
    results = await searcher.search(
        query=request.query,
        vault=request.vault,
        category=request.category,
        person=request.person,
        limit=request.limit,
        mode=mode
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
    """RAG query with LLM-generated answer."""
    global searcher
    
    import time
    start = time.time()
    
    answer, sources = await searcher.query_with_llm(
        question=request.question,
        vault=request.vault
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


async def _run_indexing_job(job_id: str, full: bool, vault: str, callback_url: Optional[str]):
    """Background task to run indexing and send callback."""
    global indexer, jobs
    
    jobs[job_id]["status"] = JobStatus.RUNNING
    start = time.time()
    
    try:
        if full:
            indexed = await indexer.full_reindex(vault=vault)
        else:
            indexed = await indexer.incremental_index(vault=vault)
        
        duration_ms = int((time.time() - start) * 1000)
        
        jobs[job_id].update({
            "status": JobStatus.COMPLETED,
            "completed_at": time.time(),
            "duration_ms": duration_ms,
            "indexed": indexed,
        })
        
        # Send callback if URL provided
        if callback_url:
            callback_payload = {
                "job_id": job_id,
                "status": "completed",
                "stats": {
                    "indexed": indexed,
                    "duration_ms": duration_ms,
                    "vault": vault,
                    "full": full,
                }
            }
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(callback_url, json=callback_payload, timeout=30.0)
                    logger.info(f"Job {job_id}: callback sent to {callback_url}")
            except Exception as e:
                logger.error(f"Job {job_id}: callback failed: {e}")
    
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        error_msg = str(e)
        
        jobs[job_id].update({
            "status": JobStatus.FAILED,
            "completed_at": time.time(),
            "duration_ms": duration_ms,
            "error": error_msg,
        })
        
        logger.error(f"Job {job_id} failed: {error_msg}")
        
        # Send failure callback if URL provided
        if callback_url:
            callback_payload = {
                "job_id": job_id,
                "status": "failed",
                "error": error_msg,
                "stats": {
                    "duration_ms": duration_ms,
                    "vault": vault,
                    "full": full,
                }
            }
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(callback_url, json=callback_payload, timeout=30.0)
                    logger.info(f"Job {job_id}: failure callback sent to {callback_url}")
            except Exception as ce:
                logger.error(f"Job {job_id}: failure callback failed: {ce}")


@app.post("/index/start", response_model=AsyncIndexStartResponse)
async def start_indexing(request: AsyncIndexRequest, background_tasks: BackgroundTasks):
    """Start async indexing job. Returns immediately with job_id."""
    global jobs
    
    job_id = str(uuid.uuid4())
    
    jobs[job_id] = {
        "status": JobStatus.PENDING,
        "started_at": time.time(),
        "completed_at": None,
        "duration_ms": None,
        "indexed": None,
        "error": None,
        "vault": request.vault,
        "full": request.full,
        "callback_url": request.callback_url,
    }
    
    # Schedule background task
    background_tasks.add_task(
        _run_indexing_job,
        job_id=job_id,
        full=request.full,
        vault=request.vault,
        callback_url=request.callback_url
    )
    
    logger.info(f"Started indexing job {job_id} (vault={request.vault}, full={request.full})")
    
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
    
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"].value,
        started_at=datetime.fromtimestamp(job["started_at"]).isoformat() if job["started_at"] else None,
        completed_at=datetime.fromtimestamp(job["completed_at"]).isoformat() if job["completed_at"] else None,
        duration_ms=job["duration_ms"],
        indexed=job["indexed"],
        error=job["error"],
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


@app.post("/index/init")
async def init_index():
    """Initialize LanceDB tables."""
    global indexer
    
    await indexer.init_tables()
    return {"status": "initialized"}


@app.get("/stats")
async def get_stats():
    """Get indexing statistics."""
    global db
    
    stats = {
        "tables": db.table_names(),
        "work_vectors": 0,
        "personal_vectors": 0,
    }
    
    try:
        if "work" in db.table_names():
            stats["work_vectors"] = db.open_table("work").count_rows()
        if "personal" in db.table_names():
            stats["personal_vectors"] = db.open_table("personal").count_rows()
    except:
        pass
    
    return stats
