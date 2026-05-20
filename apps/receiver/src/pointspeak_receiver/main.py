from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

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


class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class Selector(BaseModel):
    type: Literal["testid", "aria", "css", "xpath", "text", "domPath"]
    value: str
    confidence: float | None = None


class ElementRef(BaseModel):
    elementRef: str
    timestampMs: float = 0
    url: str
    role: str | None = None
    name: str | None = None
    text: str | None = None
    tagName: str | None = None
    boundingBox: BoundingBox | None = None
    selectors: list[Selector] = Field(default_factory=list)
    domPath: str | None = None
    stateHash: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


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


class AddElementRequest(BaseModel):
    element: ElementRef


class AddElementResponse(BaseModel):
    sessionId: str
    elementRef: str
    elementsPath: str
    handoff: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def session_dir(session_id: str) -> Path:
    return DEFAULT_STORAGE_ROOT / session_id / "session.pointspeak"


def require_session_root(session_id: str) -> Path:
    root = session_dir(session_id)
    if not (root / "manifest.json").exists():
        raise HTTPException(status_code=404, detail="Session not found")
    return root


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_hex(path.read_bytes())


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_ndjson(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(data, sort_keys=True) + "\n")


def read_ndjson(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def decode_data_url(data_url: str) -> bytes:
    prefix = "base64,"
    if prefix not in data_url:
        raise HTTPException(status_code=400, detail="Expected base64 data URL")
    try:
        return base64.b64decode(data_url.split(prefix, 1)[1], validate=True)
    except binascii.Error as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 screenshot data") from exc


def load_page(root: Path) -> dict[str, Any]:
    page_path = root / "page.json"
    if not page_path.exists():
        return {}
    return json.loads(page_path.read_text(encoding="utf-8"))


def element_label(element: dict[str, Any]) -> str:
    parts = [element.get("elementRef", "element")]
    role = element.get("role") or element.get("tagName")
    name = element.get("name") or element.get("text")
    if role:
        parts.append(str(role))
    if name:
        parts.append(json.dumps(str(name)[:120]))
    return ": ".join([parts[0], " ".join(parts[1:])]) if len(parts) > 1 else parts[0]


def render_handoff(session_id: str, root: Path, media: list[str]) -> str:
    page = load_page(root)
    elements = read_ndjson(root / "elements.ndjson")
    screenshot_line = f"- Screenshot: {root / media[0]}" if media else "- Screenshot: _not captured_"
    title = page.get("title") or session_id
    viewport = page.get("viewport") or {}
    scroll = page.get("scroll") or {}
    element_lines: list[str] = []
    for element in elements:
        selectors = element.get("selectors") or []
        selector_lines = "\n".join(
            f"  - {selector.get('type')}: `{selector.get('value')}`" for selector in selectors[:4]
        )
        bbox = element.get("boundingBox") or {}
        bbox_text = (
            f"x={bbox.get('x')}, y={bbox.get('y')}, w={bbox.get('width')}, h={bbox.get('height')}"
            if bbox
            else "not captured"
        )
        element_lines.append(f"- {element_label(element)}\n  - bbox: {bbox_text}\n{selector_lines}".rstrip())
    referenced_elements = "\n".join(element_lines) if element_lines else "_None captured yet. Use element pick mode after snapshot capture._"

    return f"""# PointSpeak Brief: {title}

## User Request
_No user note captured yet. Milestone 2 captures selected elements only._

## Page
- URL: {page.get('url', '')}
- Title: {page.get('title', '')}
- Viewport: {viewport.get('width', '')}x{viewport.get('height', '')} @ {viewport.get('devicePixelRatio', '')}
- Scroll: {scroll.get('x', '')}, {scroll.get('y', '')}
- Captured At: {page.get('capturedAt', '')}

## Referenced Elements
{referenced_elements}

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


def write_manifest(root: Path, session_id: str, mode: str, source: str, media: list[str], created_at: str | None = None) -> None:
    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "sessionId": session_id,
        "createdAt": created_at or utc_now(),
        "updatedAt": utc_now(),
        "mode": mode,
        "source": source,
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


def load_manifest(root: Path) -> dict[str, Any]:
    return json.loads((root / "manifest.json").read_text(encoding="utf-8"))


def refresh_handoff_and_manifest(root: Path, session_id: str) -> None:
    manifest = load_manifest(root)
    media = list(manifest.get("media") or [])
    handoff_dir = root / "handoff"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    (handoff_dir / "latest.md").write_text(render_handoff(session_id, root, media), encoding="utf-8")
    write_json(
        handoff_dir / "latest.json",
        {
            "schemaVersion": SCHEMA_VERSION,
            "sessionId": session_id,
            "bundlePath": str(root),
            "page": load_page(root),
            "media": media,
            "elements": read_ndjson(root / "elements.ndjson"),
        },
    )
    write_manifest(
        root,
        session_id=session_id,
        mode=str(manifest.get("mode", "snapshot")),
        source=str(manifest.get("source", "unknown")),
        media=media,
        created_at=str(manifest.get("createdAt") or utc_now()),
    )


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

    write_manifest(root, session_id=session_id, mode=req.mode, source=req.source, media=media)
    refresh_handoff_and_manifest(root, session_id)

    return CreateSessionResponse(
        sessionId=session_id,
        bundlePath=str(root),
        handoff=str(handoff_dir / "latest.md"),
        manifest=str(root / "manifest.json"),
    )


@app.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, object]:
    root = require_session_root(session_id)
    return {
        "sessionId": session_id,
        "bundlePath": str(root),
        "manifest": load_manifest(root),
        "elements": read_ndjson(root / "elements.ndjson"),
    }


@app.post("/sessions/{session_id}/elements", response_model=AddElementResponse)
def add_element(session_id: str, req: AddElementRequest) -> AddElementResponse:
    root = require_session_root(session_id)
    element_data = req.element.model_dump(mode="json", exclude_none=True)
    append_ndjson(root / "elements.ndjson", element_data)
    append_ndjson(
        root / "timeline.ndjson",
        {
            "eventId": f"t_{uuid.uuid4().hex}",
            "timestampMs": req.element.timestampMs,
            "type": "element.selected",
            "stateHash": req.element.stateHash,
            "data": {"elementRef": req.element.elementRef},
        },
    )
    refresh_handoff_and_manifest(root, session_id)
    return AddElementResponse(
        sessionId=session_id,
        elementRef=req.element.elementRef,
        elementsPath=str(root / "elements.ndjson"),
        handoff=str(root / "handoff" / "latest.md"),
    )


@app.get("/sessions/{session_id}/handoff.md", response_class=PlainTextResponse)
def get_handoff(session_id: str) -> str:
    handoff_path = require_session_root(session_id) / "handoff" / "latest.md"
    if not handoff_path.exists():
        raise HTTPException(status_code=404, detail="Handoff not found")
    return handoff_path.read_text(encoding="utf-8")


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=48321)
