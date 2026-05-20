from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DEFAULT_STORAGE_ROOT = Path(os.environ.get("POINTSPEAK_HOME", Path.home() / ".pointspeak" / "sessions"))

app = FastAPI(title="PointSpeak Receiver", version="0.1.0")


class Viewport(BaseModel):
    width: int
    height: int
    devicePixelRatio: float = 1


class Scroll(BaseModel):
    x: float = 0
    y: float = 0


class PageMetadata(BaseModel):
    url: str
    title: str | None = None
    viewport: Viewport
    scroll: Scroll = Field(default_factory=Scroll)
    capturedAt: str


class CreateSessionRequest(BaseModel):
    mode: Literal["snapshot", "walkthrough", "live"] = "snapshot"
    source: str = "chrome-extension"
    page: PageMetadata
    screenshotDataUrl: str | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def session_dir(session_id: str) -> Path:
    return DEFAULT_STORAGE_ROOT / session_id / "session.pointspeak"


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def decode_data_url(data_url: str) -> bytes:
    prefix = "base64,"
    if prefix not in data_url:
        raise HTTPException(status_code=400, detail="Expected base64 data URL")
    return base64.b64decode(data_url.split(prefix, 1)[1])


def render_handoff(session_id: str, root: Path, req: CreateSessionRequest) -> str:
    return f"""# PointSpeak Brief: {req.page.title or session_id}

## User Request
_No user note captured yet. Milestone 0 snapshot shell._

## Page
- URL: {req.page.url}
- Title: {req.page.title or ''}
- Viewport: {req.page.viewport.width}x{req.page.viewport.height} @ {req.page.viewport.devicePixelRatio}

## Referenced Elements
_None captured yet._

## Artifacts
- Bundle: {root}
- Screenshot: {root / 'media' / 'screenshot.png'}
"""


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "pointspeak-receiver"}


@app.post("/sessions")
def create_session(req: CreateSessionRequest) -> dict[str, str]:
    session_id = f"ps_{uuid.uuid4().hex}"
    root = session_dir(session_id)
    media_dir = root / "media"
    handoff_dir = root / "handoff"
    media_dir.mkdir(parents=True, exist_ok=True)
    handoff_dir.mkdir(parents=True, exist_ok=True)

    media: list[str] = []
    if req.screenshotDataUrl:
        screenshot_path = media_dir / "screenshot.png"
        screenshot_path.write_bytes(decode_data_url(req.screenshotDataUrl))
        media.append("media/screenshot.png")

    manifest = {
        "schemaVersion": "0.1.0",
        "sessionId": session_id,
        "createdAt": utc_now(),
        "mode": req.mode,
        "source": req.source,
        "page": "page.json",
        "timeline": "timeline.ndjson",
        "annotations": "annotations.ndjson",
        "elements": "elements.ndjson",
        "media": media,
        "handoff": "handoff/latest.md",
    }

    write_json(root / "manifest.json", manifest)
    write_json(root / "page.json", req.page.model_dump(mode="json"))
    write_json(root / "privacy-report.json", {
        "schemaVersion": "0.1.0",
        "createdAt": utc_now(),
        "defaults": {
            "localOnly": True,
            "cookiesCaptured": False,
            "authorizationHeadersCaptured": False,
            "networkBodiesCaptured": False,
        },
        "warnings": [],
    })
    (root / "timeline.ndjson").write_text(json.dumps({
        "eventId": "t1",
        "timestampMs": 0,
        "type": "snapshot.captured",
        "media": "media/screenshot.png" if media else None,
    }) + "\n", encoding="utf-8")
    (root / "annotations.ndjson").write_text("", encoding="utf-8")
    (root / "elements.ndjson").write_text("", encoding="utf-8")

    handoff_md = render_handoff(session_id, root, req)
    (handoff_dir / "latest.md").write_text(handoff_md, encoding="utf-8")
    write_json(handoff_dir / "latest.json", {
        "sessionId": session_id,
        "bundlePath": str(root),
        "page": req.page.model_dump(mode="json"),
        "media": media,
    })

    return {"sessionId": session_id, "bundlePath": str(root), "handoff": str(handoff_dir / "latest.md")}


@app.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, object]:
    root = session_dir(session_id)
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    return {"sessionId": session_id, "bundlePath": str(root), "manifest": json.loads(manifest_path.read_text())}


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=48321)
