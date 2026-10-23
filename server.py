import os
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Query, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

import db
from engine import engine
from config import load_config

app = FastAPI(title="AI Job Searcher API", version="2.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

@app.on_event("startup")
def on_startup():
    db.init_db()

@app.get("/api/jobs")
def get_jobs_api(
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    search: Optional[str] = Query(None),
    min_score: Optional[int] = Query(None),
    remote_only: bool = Query(False),
    platform: Optional[str] = Query(None),
    sort_by: str = Query("score")
):
    """Paginated jobs API for infinite scrolling and dynamic filtering."""
    result = db.get_jobs(
        page=page,
        limit=limit,
        search=search,
        min_score=min_score,
        remote_only=remote_only,
        platform=platform,
        sort_by=sort_by
    )
    return result

@app.get("/api/stats")
def get_stats_api():
    """Aggregate statistics for match scores, platforms, and totals."""
    return db.get_stats()

@app.get("/api/status")
def get_status_api():
    """Real-time progress of background scraper and LLM evaluator."""
    return engine.get_status()

@app.post("/api/refresh")
def trigger_refresh_api(limit_eval: int = Query(30), continuous: bool = Query(True)):
    """Triggers background scraping and progressive Ollama matching."""
    started = engine.start_refresh_async(limit_evaluations=limit_eval, continuous_batch=continuous)
    if started:
        return {"success": True, "message": "Scrape and AI evaluation started in background"}
    else:
        return {"success": False, "message": "Scraper or evaluator is already running"}

@app.post("/api/analyze-all")
def trigger_batch_analysis_api(batch_size: int = Query(10, ge=1, le=50)):
    """Triggers background batch LLM evaluation on all remaining unassessed jobs."""
    started = engine.start_batch_evaluator_async(batch_size=batch_size)
    if started:
        return {"success": True, "message": "Batch AI evaluation started in background"}
    else:
        return {"success": False, "message": "Scraper or evaluator is already in progress"}

@app.post("/api/stop")
def stop_engine_api():
    """Pauses or stops current background scraping or batch evaluation."""
    stopped = engine.stop()
    return {"success": stopped, "message": "Stop signal sent to background task" if stopped else "No background task running"}

@app.post("/api/reset")
def reset_database_api(clear_files: bool = Query(False)):
    """Wipes the SQLite database and optionally clears exported results files."""
    db.clear_db()
    if clear_files:
        results_dir = Path(__file__).parent / "results"
        if results_dir.exists():
            for f in results_dir.glob("jobs_*.*"):
                try:
                    f.unlink()
                except Exception:
                    pass
    return {"success": True, "message": "Database and records reset successfully"}

@app.get("/")
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return JSONResponse({"status": "Frontend loading", "message": "index.html not created yet"})
    return FileResponse(index_file)

# Mount remaining static assets
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
