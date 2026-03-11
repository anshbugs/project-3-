from __future__ import annotations

import logging
import threading
import uuid
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .main import run_pipeline

logger = logging.getLogger(__name__)

app = FastAPI(title="GROWW Weekly Pulse API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_job_status: Dict[str, Dict[str, Any]] = {}


def _run_pipeline_background(
    job_id: str,
    phase: str,
    weeks: Optional[int],
    max_reviews: Optional[int],
    date: Optional[str],
    recipient: Optional[str],
    recipient_name: Optional[str],
    send: bool,
) -> None:
    import os
    import time
    start_delay = int(os.getenv("GROWW_PIPELINE_START_DELAY", "0"))
    if start_delay > 0:
        logger.info("Waiting %s seconds before pipeline (container warm-up)", start_delay)
        time.sleep(start_delay)
    try:
        _job_status[job_id] = {"status": "running", "message": "Pipeline started."}
        run_pipeline(
            phase=phase,
            weeks=weeks,
            max_reviews=max_reviews,
            report_date_str=date,
            recipient=recipient,
            recipient_name=recipient_name,
            send=send,
        )
        _job_status[job_id] = {"status": "completed", "message": "Pipeline finished successfully."}
    except Exception as exc:
        logger.exception("Pipeline job %s failed", job_id)
        err_msg = str(exc)
        if "101" in err_msg or "Network is unreachable" in err_msg or "Network unreachable" in err_msg:
            err_msg = (
                "Backend could not reach the internet (OpenRouter or email). "
                "On Render free tier, ensure the service allows outbound HTTPS; "
                "or run the pipeline locally / via GitHub Actions."
            )
        _job_status[job_id] = {"status": "failed", "error": err_msg}


class RunRequest(BaseModel):
    phase: str = "all"
    weeks: Optional[int] = None
    max_reviews: Optional[int] = None
    date: Optional[str] = None
    recipient: Optional[str] = None
    recipient_name: Optional[str] = None
    send: bool = False


class RunResponse(BaseModel):
    status: str
    job_id: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    message: Optional[str] = None
    error: Optional[str] = None


@app.post("/api/run", response_model=RunResponse, status_code=202)
def run(request: RunRequest) -> RunResponse:
    """Start the pipeline in the background. Returns immediately. Poll GET /api/run/status/{job_id} for completion."""
    job_id = str(uuid.uuid4())
    _job_status[job_id] = {"status": "pending", "message": "Job queued."}

    thread = threading.Thread(
        target=_run_pipeline_background,
        kwargs={
            "job_id": job_id,
            "phase": request.phase,
            "weeks": request.weeks,
            "max_reviews": request.max_reviews,
            "date": request.date,
            "recipient": request.recipient,
            "recipient_name": request.recipient_name,
            "send": request.send,
        },
    )
    thread.daemon = True
    thread.start()

    return RunResponse(
        status="accepted",
        job_id=job_id,
        message="Pipeline started. Poll /api/run/status/" + job_id + " for status.",
    )


@app.get("/api/run/status/{job_id}", response_model=JobStatusResponse)
def get_run_status(job_id: str) -> JobStatusResponse:
    if job_id not in _job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    rec = _job_status[job_id]
    return JobStatusResponse(
        job_id=job_id,
        status=rec["status"],
        message=rec.get("message"),
        error=rec.get("error"),
    )


@app.get("/")
def root() -> dict:
    """Root route so the backend URL does not return 404."""
    return {
        "service": "GROWW Weekly Pulse API",
        "docs": "/docs",
        "health": "/api/health",
        "run": "POST /api/run",
    }


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
