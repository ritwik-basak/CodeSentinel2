from __future__ import annotations

import sys
import os

# Add project root to Python path so all core modules are findable
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

"""
api/main.py — FastAPI backend with SSE streaming.

Endpoints
---------
POST /review                         Start a new review (returns review_id)
GET  /review/{review_id}/stream      SSE stream of progress events
GET  /review/{review_id}/report      Final structured report (JSON)
GET  /health                         Health check
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

load_dotenv()

app = FastAPI(title="Code Review API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory review store
# reviews[review_id] = {
#   "status":  "running" | "complete" | "error"
#   "events":  list of SSE event dicts
#   "report":  dict | None
# }
# ---------------------------------------------------------------------------

reviews: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ReviewRequest(BaseModel):
    repo_url: str


# ---------------------------------------------------------------------------
# Background runner
# ---------------------------------------------------------------------------

async def _run_review_task(review_id: str, repo_url: str) -> None:
    """
    Async task.  Imports core.graph inside the function (not at module level)
    so the import resolves in the correct runtime context, then runs the
    blocking pipeline in a thread-pool executor so it doesn't block the
    event loop.
    """
    import sys
    import os
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

    def _sync_run() -> None:
        from core.graph import run_review_stream

        try:
            for event in run_review_stream(review_id, repo_url):
                reviews[review_id]["events"].append(event)

                if event.get("type") == "complete":
                    reviews[review_id]["report"] = event.get("report", {})
                    reviews[review_id]["status"] = "complete"

                elif event.get("type") == "error":
                    reviews[review_id]["status"] = "error"

        except Exception as exc:
            reviews[review_id]["events"].append({
                "type":      "error",
                "step":      "runner",
                "status":    "error",
                "message":   str(exc),
                "timestamp": datetime.now().isoformat(),
            })
            reviews[review_id]["status"] = "error"

        finally:
            if reviews[review_id]["status"] == "running":
                reviews[review_id]["status"] = "complete"

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _sync_run)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/review")
async def start_review(request: ReviewRequest) -> dict[str, str]:
    """Start a new code review.  Returns review_id immediately."""
    review_id = uuid.uuid4().hex[:8]

    reviews[review_id] = {
        "status": "running",
        "events": [],
        "report": None,
    }

    asyncio.create_task(_run_review_task(review_id, request.repo_url))

    return {"review_id": review_id, "status": "started"}


@app.get("/review/{review_id}/stream")
async def stream_review(review_id: str) -> EventSourceResponse:
    """
    SSE endpoint.  Streams progress events as they are produced by the
    background thread.  Closes automatically when the review finishes.
    """
    if review_id not in reviews:
        raise HTTPException(status_code=404, detail="Review not found")

    async def event_generator():
        sent = 0
        while True:
            review = reviews[review_id]
            events = review["events"]

            # Drain any new events
            while sent < len(events):
                yield {"data": json.dumps(events[sent])}
                sent += 1

            # Stop once the thread is done
            if review["status"] in ("complete", "error"):
                # Flush any last events that arrived just before status changed
                while sent < len(events):
                    yield {"data": json.dumps(events[sent])}
                    sent += 1
                return

            await asyncio.sleep(0.4)

    return EventSourceResponse(event_generator())


@app.get("/review/{review_id}/report")
async def get_report(review_id: str) -> dict[str, Any]:
    """Return the final structured report once the review is complete."""
    if review_id not in reviews:
        raise HTTPException(status_code=404, detail="Review not found")

    review = reviews[review_id]

    if review["status"] == "running":
        raise HTTPException(status_code=202, detail="Review still in progress")

    if review["status"] == "error":
        raise HTTPException(status_code=500, detail="Review failed — check /stream for details")

    return review["report"] or {}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "code-review-api"}
