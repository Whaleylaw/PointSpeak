from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

DEFAULT_STORAGE_ROOT = Path(os.environ.get("POINTSPEAK_HOME", Path.home() / ".pointspeak" / "sessions"))
SCHEMA_VERSION = "0.1.0"

app = FastAPI(title="PointSpeak Receiver", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


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


class CreateSessionResponse(BaseModel):
    sessionId: str
    bundlePath: str
    handoff: str
    manifest: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def session_dir(session_id: str) -> Path:
    return DEFAULT_STORAGE_ROOT / session_id / "session.pointspeak"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_hex(path.read_bytes())


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def decode_data_url(data_url: str) -> bytes:
    prefix = "base64,"
    if prefix not in data_url:
        raise HTTPException(status_code=400, detail="Expected base64 data URL")
    try:
        return base64.b64decode(data_url.split(prefix, 1)[1], validate=True)
    except binascii.Error as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 screenshot data") from exc


def render_handoff(session_id: str, root: Path, req: CreateSessionRequest, media: list[str]) -> str:
    screenshot_line = f"- Screenshot: {root / media[0]}" if media else "- Screenshot: _not captured_"
    return f"""# PointSpeak Brief: {req.page.title or session_id}

## User Request
_No user note captured yet. Milestone 1 snapshot capture only._

## Page
- URL: {req.page.url}
- Title: {req.page.title or ''}
- Viewport: {req.page.viewport.width}x{req.page.viewport.height} @ {req.page.viewport.devicePixelRatio}
- Scroll: {req.page.scroll.x}, {req.page.scroll.y}
- Captured At: {req.page.capturedAt}

## Referenced Elements
_None captured yet. Element selection starts in Milestone 2._

## Annotations
_None captured yet. Annotation overlay starts in Milestone 3._

## Artifacts
- Session ID: {session_id}
- Bundle: {root}
{screenshot_line}
- Manifest: {root / 'manifest.json'}
"""


def init_empty_bundle_files(root: Path) -> None:
    (root / "annotations.ndjson").write_text("", encoding="utf-8")
    (root / "elements.ndjson").write_text("", encoding="utf-8")


def build_file_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        hashes[str(path.relative_to(root))] = file_sha256(path)
    return hashes


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "pointspeak-receiver", "schemaVersion": SCHEMA_VERSION}


@app.post("/sessions", response_model=CreateSessionResponse)
def create_session(req: CreateSessionRequest) -> CreateSessionResponse:
    session_id = f"ps_{uuid.uuid4().hex}"
    root = session_dir(session_id)
    media_dir = root / "media"
    handoff_dir = root / "handoff"
    media_dir.mkdir(parents=True, exist_ok=True)
    handoff_dir.mkdir(parents=True, exist_ok=True)

    media: list[str] = []
    visual_hash: str | None = None
    screenshot_size: int | None = None
    if req.screenshotDataUrl:
        screenshot_bytes = decode_data_url(req.screenshotDataUrl)
        screenshot_size = len(screenshot_bytes)
        visual_hash = sha256_hex(screenshot_bytes)
        screenshot_path = media_dir / "screenshot.png"
        screenshot_path.write_bytes(screenshot_bytes)
        media.append("media/screenshot.png")

    write_json(root / "page.json", req.page.model_dump(mode="json"))
    write_json(
        root / "privacy-report.json",
        {
            "schemaVersion": SCHEMA_VERSION,
            "createdAt": utc_now(),
            "defaults": {
                "localOnly": True,
                "cookiesCaptured": False,
                "authorizationHeadersCaptured": False,
                "networkBodiesCaptured": False,
                "domCaptured": False,
                "audioCaptured": False,
            },
            "warnings": [],
        },
    )
    timeline_event = {
        "eventId": "t1",
        "timestampMs": 0,
        "type": "snapshot.captured",
        "media": media[0] if media else None,
        "visualHash": visual_hash,
        "data": {"screenshotBytes": screenshot_size} if screenshot_size is not None else {},
    }
    (root / "timeline.ndjson").write_text(json.dumps(timeline_event, sort_keys=True) + "\n", encoding="utf-8")
    init_empty_bundle_files(root)

    handoff_md = render_handoff(session_id, root, req, media)
    (handoff_dir / "latest.md").write_text(handoff_md, encoding="utf-8")
    write_json(
        handoff_dir / "latest.json",
        {
            "schemaVersion": SCHEMA_VERSION,
            "sessionId": session_id,
            "bundlePath": str(root),
            "page": req.page.model_dump(mode="json"),
            "media": media,
            "visualHash": visual_hash,
        },
    )

    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "sessionId": session_id,
        "createdAt": utc_now(),
        "mode": req.mode,
        "source": req.source,
        "page": "page.json",
        "timeline": "timeline.ndjson",
        "annotations": "annotations.ndjson",
        "elements": "elements.ndjson",
        "privacyReport": "privacy-report.json",
        "media": media,
        "handoff": "handoff/latest.md",
        "hashes": build_file_hashes(root),
    }
    write_json(root / "manifest.json", manifest)

    return CreateSessionResponse(
        sessionId=session_id,
        bundlePath=str(root),
        handoff=str(handoff_dir / "latest.md"),
        manifest=str(root / "manifest.json"),
    )


@app.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, object]:
    root = session_dir(session_id)
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    return {"sessionId": session_id, "bundlePath": str(root), "manifest": json.loads(manifest_path.read_text())}


@app.get("/sessions/{session_id}/handoff.md", response_class=PlainTextResponse)
def get_handoff(session_id: str) -> str:
    handoff_path = session_dir(session_id) / "handoff" / "latest.md"
    if not handoff_path.exists():
        raise HTTPException(status_code=404, detail="Handoff not found")
    return handoff_path.read_text(encoding="utf-8")


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=48321)
