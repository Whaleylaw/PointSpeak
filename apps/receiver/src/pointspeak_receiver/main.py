from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import urllib.error
import urllib.request
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
DEFAULT_HERMES_API_URL = os.environ.get("POINTSPEAK_HERMES_API_URL", "http://127.0.0.1:8642")
DEFAULT_HERMES_MODEL = os.environ.get("POINTSPEAK_HERMES_MODEL", "hermes-agent")
DEFAULT_HERMES_TIMEOUT_SECONDS = float(os.environ.get("POINTSPEAK_HERMES_TIMEOUT_SECONDS", "3"))
DEFAULT_DESKTOP_INBOX = Path(os.environ.get("POINTSPEAK_DESKTOP_INBOX", Path.home() / "Github" / "RoscoeDesktop" / ".pointspeak-inbox"))
DEFAULT_BRIDGE_ROOT = Path(os.environ.get("POINTSPEAK_BRIDGE_ROOT", DEFAULT_STORAGE_ROOT.parent / "bridge"))
DEFAULT_STT_MODEL = os.environ.get("POINTSPEAK_STT_MODEL", "base")

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


class AnnotationShape(BaseModel):
    x: float
    y: float
    width: float
    height: float
    pageX: float | None = None
    pageY: float | None = None
    coordinateSpace: Literal["viewport", "page", "screenshot"] = "viewport"


class Annotation(BaseModel):
    annotationId: str
    type: Literal["rectangle", "arrow", "freehand", "text", "pin"]
    timestampMs: float = 0
    text: str | None = None
    targetElementRefs: list[str] = Field(default_factory=list)
    color: str | None = None
    shape: AnnotationShape | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Narration(BaseModel):
    narrationId: str
    timestampMs: float = 0
    durationMs: float | None = None
    transcript: str | None = None
    audioDataUrl: str | None = None
    mimeType: str = "audio/webm"
    targetElementRefs: list[str] = Field(default_factory=list)
    targetAnnotationRefs: list[str] = Field(default_factory=list)
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


class AddAnnotationRequest(BaseModel):
    annotation: Annotation


class AddAnnotationResponse(BaseModel):
    sessionId: str
    annotationId: str
    annotationsPath: str
    handoff: str


class AddNarrationRequest(BaseModel):
    narration: Narration


class AddNarrationResponse(BaseModel):
    sessionId: str
    narrationId: str
    audioPath: str | None = None
    narrationsPath: str
    handoff: str


class SubmitHandoffRequest(BaseModel):
    dryRun: bool = False
    hermesApiUrl: str | None = None
    model: str | None = None
    instructions: str | None = None


class SubmitHandoffResponse(BaseModel):
    sessionId: str
    status: Literal["dry_run", "submitted", "failed"]
    runId: str | None = None
    hermesApiUrl: str
    requestPath: str
    handoff: str
    error: str | None = None


def bridge_wake_instructions(lease: dict[str, Any]) -> str:
    notify_target = str(lease.get("notifyTarget") or os.environ.get("POINTSPEAK_NOTIFY_TARGET") or "telegram").strip()
    return (
        "You are Coder receiving a live PointSpeak visual briefing through an active bridge lease. "
        "Treat this as a user-initiated message from Aaron, not a passive background artifact. "
        "Read the bundle/intake/replay paths in the prompt, summarize what Aaron pointed at, include any narration transcript, "
        "and propose or take the next concrete coding/debugging step if it is safe and obvious. "
        f"Before your final response, use the messaging/send_message tool to send your concise response to `{notify_target}` so Aaron's current chat is woken up. "
        "If that tool is unavailable, say so in your final response and still provide the analysis."
    )


class RedactionRegion(BaseModel):
    redactionId: str
    reason: str = "user-selected"
    shape: AnnotationShape
    replacement: str = "masked"


class PrivacyControls(BaseModel):
    redactTextPatterns: bool = True
    redactEmails: bool = True
    redactPhones: bool = True
    redactCreditCards: bool = True
    redactSecrets: bool = True
    screenshotRegions: list[RedactionRegion] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class UpdatePrivacyControlsRequest(BaseModel):
    controls: PrivacyControls


class IntakeResponse(BaseModel):
    sessionId: str
    intakePath: str
    actionDraftPath: str
    replayPath: str
    summary: str
    suggestedActions: list[str]
    redactionsApplied: list[str] = Field(default_factory=list)


class ReplayResponse(BaseModel):
    sessionId: str
    replayPath: str


class DesktopExportResponse(BaseModel):
    sessionId: str
    exportPath: str
    desktopInbox: str


class BridgeActivateRequest(BaseModel):
    agent: str
    ttlMinutes: int = Field(default=30, ge=1, le=24 * 60)
    hermesApiUrl: str | None = None
    apiKeyEnv: str | None = None
    model: str | None = None
    notifyTarget: str | None = None
    wakeChat: bool = True
    includeBacklogMinutes: int = Field(default=0, ge=0, le=7 * 24 * 60)


class BridgeReleaseRequest(BaseModel):
    agent: str | None = None


class BridgeQueueRequest(BaseModel):
    sessionId: str
    target: str | None = None
    status: Literal["queued", "delivered", "failed"] = "queued"


class BridgeEventResponse(BaseModel):
    eventId: str
    sessionId: str
    bundlePath: str
    target: str
    status: str
    activeAgent: str | None = None
    deliveryStatus: str | None = None
    deliveryError: str | None = None


class BridgeFinalizeResponse(BaseModel):
    sessionId: str
    bridge: BridgeEventResponse
    intake: IntakeResponse
    desktop: DesktopExportResponse
    handoff: SubmitHandoffResponse | None = None


def parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def bridge_dir() -> Path:
    DEFAULT_BRIDGE_ROOT.mkdir(parents=True, exist_ok=True)
    (DEFAULT_BRIDGE_ROOT / "inbox").mkdir(parents=True, exist_ok=True)
    return DEFAULT_BRIDGE_ROOT


def bridge_state_path() -> Path:
    return bridge_dir() / "state.json"


def bridge_events_path() -> Path:
    return bridge_dir() / "events.ndjson"


def normalize_target(value: str | None) -> str:
    target = (value or "unclaimed").strip().lower().replace(" ", "-")
    return "".join(ch for ch in target if ch.isalnum() or ch in {"-", "_"}) or "unclaimed"


def load_bridge_state() -> dict[str, Any]:
    path = bridge_state_path()
    if not path.exists():
        return {"activeLease": None, "updatedAt": utc_now()}
    return json.loads(path.read_text(encoding="utf-8"))


def active_bridge_lease() -> dict[str, Any] | None:
    state = load_bridge_state()
    lease = state.get("activeLease")
    if not lease:
        return None
    expires = parse_utc(lease.get("expiresAt"))
    if not expires or expires <= datetime.now(timezone.utc):
        state["activeLease"] = None
        state["updatedAt"] = utc_now()
        write_json(bridge_state_path(), state)
        return None
    return lease


def bridge_inbox_path(target: str) -> Path:
    return bridge_dir() / "inbox" / f"{normalize_target(target)}.ndjson"


def read_bridge_events(target: str | None = None, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    rows = read_ndjson(bridge_events_path())
    if target:
        rows = [row for row in rows if row.get("target") == normalize_target(target)]
    if status:
        rows = [row for row in rows if row.get("status") == status]
    return rows[-limit:]


def append_bridge_event(event: dict[str, Any]) -> None:
    append_ndjson(bridge_events_path(), event)
    append_ndjson(bridge_inbox_path(str(event.get("target") or "unclaimed")), event)


def build_bridge_event(session_id: str, root: Path, target: str, status: str = "queued", delivery: SubmitHandoffResponse | None = None) -> dict[str, Any]:
    intake_path = root / "handoff" / "intake.json"
    action_path = root / "handoff" / "action-draft.md"
    replay_path = root / "replay" / "index.html"
    return {
        "eventId": f"evt_{uuid.uuid4().hex}",
        "createdAt": utc_now(),
        "sessionId": session_id,
        "bundlePath": str(root),
        "target": normalize_target(target),
        "status": status,
        "claimedBy": None,
        "claimedAt": None,
        "artifacts": {
            "intake": str(intake_path),
            "actionDraft": str(action_path),
            "replay": str(replay_path),
            "handoff": str(root / "handoff" / "latest.md"),
        },
        "delivery": delivery.model_dump(mode="json") if delivery else None,
    }


def queue_bridge_session(session_id: str, root: Path, target: str | None = None, delivery: SubmitHandoffResponse | None = None) -> dict[str, Any]:
    lease = active_bridge_lease()
    chosen_target = normalize_target(target or (lease or {}).get("agent") or "unclaimed")
    status = "delivered" if delivery and delivery.status == "submitted" else "queued"
    event = build_bridge_event(session_id, root, chosen_target, status=status, delivery=delivery)
    append_bridge_event(event)
    append_ndjson(
        root / "timeline.ndjson",
        {
            "eventId": f"t_{uuid.uuid4().hex}",
            "timestampMs": 0,
            "type": "bridge.queued" if status == "queued" else "bridge.delivered",
            "data": {"bridgeEventId": event["eventId"], "target": chosen_target, "status": status},
        },
    )
    return event


def bridge_response_from_event(event: dict[str, Any], lease: dict[str, Any] | None = None) -> BridgeEventResponse:
    delivery = event.get("delivery") or {}
    return BridgeEventResponse(
        eventId=str(event.get("eventId")),
        sessionId=str(event.get("sessionId")),
        bundlePath=str(event.get("bundlePath")),
        target=str(event.get("target")),
        status=str(event.get("status")),
        activeAgent=(lease or {}).get("agent") if lease else None,
        deliveryStatus=delivery.get("status"),
        deliveryError=delivery.get("error"),
    )


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


def append_ndjson(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def write_ndjson(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


def read_ndjson(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def transcribe_audio_file(audio_path: Path) -> tuple[str | None, dict[str, Any]]:
    """Best-effort local speech-to-text for captured narration audio.

    Uses faster-whisper when installed. The receiver remains local-capture-first:
    transcription failures are recorded as metadata instead of failing capture.
    """
    if os.environ.get("POINTSPEAK_STT_ENABLED", "true").lower() in {"0", "false", "no", "off"}:
        return None, {"status": "disabled"}
    try:
        from faster_whisper import WhisperModel  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - depends on optional local package
        return None, {"status": "unavailable", "provider": "faster-whisper", "error": str(exc)}
    try:  # pragma: no cover - exercised only when model/ffmpeg are locally available
        model_name = os.environ.get("POINTSPEAK_STT_MODEL", DEFAULT_STT_MODEL)
        device = os.environ.get("POINTSPEAK_STT_DEVICE", "auto")
        compute_type = os.environ.get("POINTSPEAK_STT_COMPUTE_TYPE", "auto")
        kwargs: dict[str, Any] = {}
        if device != "auto":
            kwargs["device"] = device
        if compute_type != "auto":
            kwargs["compute_type"] = compute_type
        model = WhisperModel(model_name, **kwargs)
        segments, info = model.transcribe(str(audio_path), vad_filter=True)
        transcript = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
        metadata = {
            "status": "ok" if transcript else "empty",
            "provider": "faster-whisper",
            "model": model_name,
            "language": getattr(info, "language", None),
            "languageProbability": getattr(info, "language_probability", None),
        }
        return transcript or None, metadata
    except Exception as exc:
        return None, {"status": "failed", "provider": "faster-whisper", "error": str(exc)}


def transcribe_missing_narrations(root: Path) -> None:
    narrations_path = root / "narrations.ndjson"
    narrations = read_ndjson(narrations_path)
    changed = False
    for narration in narrations:
        if narration.get("transcript") or not narration.get("audio"):
            continue
        audio_path = root / str(narration["audio"])
        if not audio_path.exists():
            narration.setdefault("metadata", {})["transcription"] = {"status": "missing-audio"}
            changed = True
            continue
        transcript, metadata = transcribe_audio_file(audio_path)
        narration.setdefault("metadata", {})["transcription"] = metadata
        if transcript:
            narration["transcript"] = transcript
        changed = True
    if changed:
        write_ndjson(narrations_path, narrations)


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


def annotation_label(annotation: dict[str, Any]) -> str:
    parts = [annotation.get("annotationId", "annotation")]
    annotation_type = annotation.get("type")
    text = annotation.get("text")
    if annotation_type:
        parts.append(str(annotation_type))
    if text:
        parts.append(json.dumps(str(text)[:160]))
    return ": ".join([parts[0], " ".join(parts[1:])]) if len(parts) > 1 else parts[0]


def narration_label(narration: dict[str, Any]) -> str:
    parts = [narration.get("narrationId", "narration")]
    duration = narration.get("durationMs")
    transcript = narration.get("transcript")
    if duration is not None:
        parts.append(f"{round(float(duration) / 1000, 1)}s")
    if transcript:
        parts.append(json.dumps(str(transcript)[:160]))
    return ": ".join([parts[0], " ".join(parts[1:])]) if len(parts) > 1 else parts[0]


def load_privacy_report(root: Path) -> dict[str, Any]:
    path = root / "privacy-report.json"
    if not path.exists():
        return {"redactionControls": PrivacyControls().model_dump(mode="json"), "redactionsApplied": []}
    return json.loads(path.read_text(encoding="utf-8"))


def redact_text(value: str | None, privacy: dict[str, Any]) -> tuple[str | None, list[str]]:
    if not value:
        return value, []
    import re

    controls = privacy.get("redactionControls") or {}
    if not controls.get("redactTextPatterns", True):
        return value, []
    redactions: list[str] = []
    text = value
    patterns: list[tuple[str, str, str]] = []
    if controls.get("redactEmails", True):
        patterns.append(("email", r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[redacted-email]"))
    if controls.get("redactPhones", True):
        patterns.append(("phone", r"(?<!\d)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\d)", "[redacted-phone]"))
    if controls.get("redactCreditCards", True):
        patterns.append(("credit-card", r"(?<!\d)(?:\d[ -]*?){13,19}(?!\d)", "[redacted-card]"))
    if controls.get("redactSecrets", True):
        patterns.extend(
            [
                ("secret", r"\b(?:api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,;]+", "[redacted-secret]"),
                ("secret-query", r"([?&](?:access_)?token=)[^\s&#]+", r"\1[redacted-secret]"),
                ("jwt", r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b", "[redacted-jwt]"),
            ]
        )
    for label, pattern, replacement in patterns:
        text, count = re.subn(pattern, replacement, text, flags=re.IGNORECASE)
        if count:
            redactions.append(label)
    return text, redactions


def sanitized_records(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    privacy = load_privacy_report(root)
    redactions: list[str] = []
    page = load_page(root)
    for key in ("url", "title"):
        page[key], found = redact_text(page.get(key), privacy)
        redactions.extend(found)

    def sanitize_row(row: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
        clean = dict(row)
        for key in keys:
            clean[key], found = redact_text(clean.get(key), privacy)
            redactions.extend(found)
        return clean

    elements = [sanitize_row(row, ("name", "text", "domPath")) for row in read_ndjson(root / "elements.ndjson")]
    annotations = [sanitize_row(row, ("text",)) for row in read_ndjson(root / "annotations.ndjson")]
    narrations = [sanitize_row(row, ("transcript",)) for row in read_ndjson(root / "narrations.ndjson")]
    return page, elements, annotations, narrations, sorted(set(redactions))


def build_capture_points(
    elements: list[dict[str, Any]], annotations: list[dict[str, Any]], narrations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_element = {row.get("elementRef"): row for row in elements}
    by_annotation = {row.get("annotationId"): row for row in annotations}
    points: list[dict[str, Any]] = []
    used_annotations: set[str] = set()
    for annotation in annotations:
        annotation_id = annotation.get("annotationId")
        target_refs = annotation.get("targetElementRefs") or []
        related_narrations = [n for n in narrations if annotation_id in (n.get("targetAnnotationRefs") or [])]
        for narration in related_narrations:
            used_annotations.add(str(annotation_id))
        points.append(
            {
                "pointId": f"point_{len(points) + 1}",
                "elements": [by_element[ref] for ref in target_refs if ref in by_element],
                "annotation": annotation,
                "narrations": related_narrations,
            }
        )
    for element in elements:
        element_ref = element.get("elementRef")
        if not any(element_ref in (p.get("annotation", {}).get("targetElementRefs") or []) for p in points):
            points.append({"pointId": f"point_{len(points) + 1}", "elements": [element], "annotation": None, "narrations": []})
    for narration in narrations:
        if not narration.get("targetAnnotationRefs"):
            points.append({"pointId": f"point_{len(points) + 1}", "elements": [], "annotation": None, "narrations": [narration]})
    return points


def build_action_draft(session_id: str, root: Path) -> dict[str, Any]:
    page, elements, annotations, narrations, redactions = sanitized_records(root)
    points = build_capture_points(elements, annotations, narrations)
    intent_parts: list[str] = []
    for annotation in annotations:
        if annotation.get("text"):
            intent_parts.append(str(annotation["text"]))
    for narration in narrations:
        if narration.get("transcript"):
            intent_parts.append(str(narration["transcript"]))
    observed_intent = " ".join(intent_parts).strip() or "User pointed at captured UI context without an explicit typed or spoken request."
    first_element = elements[0] if elements else {}
    label = first_element.get("name") or first_element.get("text") or first_element.get("role") or first_element.get("tagName") or "captured UI"
    summary = f"PointSpeak capture on {page.get('title') or page.get('url') or 'unknown page'} referencing {len(points)} point(s); primary target: {label}."
    suggested = [
        "Open the replay HTML to inspect the screenshot with annotation overlays.",
        "Use the selected element selectors to locate the owning component or test target.",
        "Translate the annotation/narration into a concrete bugfix or UX task before editing files.",
    ]
    if redactions:
        suggested.insert(0, "Review privacy redactions before sharing this bundle outside the local machine.")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "sessionId": session_id,
        "bundlePath": str(root),
        "page": page,
        "capturePoints": points,
        "observedIntent": observed_intent,
        "summary": summary,
        "suggestedActions": suggested,
        "artifacts": {
            "handoffMarkdown": str(root / "handoff" / "latest.md"),
            "handoffJson": str(root / "handoff" / "latest.json"),
            "replayHtml": str(root / "replay" / "index.html"),
            "privacyReport": str(root / "privacy-report.json"),
        },
        "redactionsApplied": redactions,
    }


def render_action_draft(intake: dict[str, Any]) -> str:
    actions = "\n".join(f"- {action}" for action in intake.get("suggestedActions", []))
    points = "\n".join(
        f"- {point['pointId']}: {len(point.get('elements') or [])} element(s), "
        f"annotation={bool(point.get('annotation'))}, narrations={len(point.get('narrations') or [])}"
        for point in intake.get("capturePoints", [])
    ) or "- none"
    return f"""# PointSpeak Action Draft

## Summary
{intake.get('summary')}

## Observed Intent
{intake.get('observedIntent')}

## Capture Points
{points}

## Suggested Next Actions
{actions}

## Artifacts
- Replay: {intake.get('artifacts', {}).get('replayHtml')}
- Handoff JSON: {intake.get('artifacts', {}).get('handoffJson')}
- Privacy Report: {intake.get('artifacts', {}).get('privacyReport')}
"""


def write_replay_html(session_id: str, root: Path) -> Path:
    page, elements, annotations, narrations, _redactions = sanitized_records(root)
    manifest = load_manifest(root)
    media = list(manifest.get("media") or [])
    screenshot = next((item for item in media if item.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))), None)
    regions = (load_privacy_report(root).get("redactionControls") or {}).get("screenshotRegions") or []
    overlay_items: list[dict[str, Any]] = []
    for element in elements:
        if element.get("boundingBox"):
            overlay_items.append({"kind": "element", "label": element.get("elementRef"), "shape": element["boundingBox"]})
    for annotation in annotations:
        if annotation.get("shape"):
            overlay_items.append({"kind": "annotation", "label": annotation.get("annotationId"), "shape": annotation["shape"]})
    for region in regions:
        if region.get("shape"):
            overlay_items.append({"kind": "redaction", "label": region.get("reason", "redacted"), "shape": region["shape"]})
    html = f"""<!doctype html>
<meta charset=\"utf-8\" />
<title>PointSpeak Replay {session_id}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; background: #111827; color: #f9fafb; }}
.stage {{ position: relative; display: inline-block; border: 1px solid #374151; background: #000; }}
.stage img {{ display: block; max-width: min(96vw, 1400px); height: auto; }}
.box {{ position: absolute; box-sizing: border-box; border: 3px solid #38bdf8; background: rgba(56,189,248,.12); color: #fff; font: 12px system-ui; padding: 2px 4px; overflow: visible; }}
.box.annotation {{ border-color: #f97316; background: rgba(249,115,22,.16); }}
.box.redaction {{ border-color: #111827; background: rgba(17,24,39,.82); }}
pre {{ white-space: pre-wrap; background: #1f2937; padding: 12px; border-radius: 8px; }}
</style>
<h1>PointSpeak Replay</h1>
<p><strong>Session:</strong> {session_id}</p>
<p><strong>Page:</strong> {page.get('title') or ''} — {page.get('url') or ''}</p>
<div class=\"stage\">
  {'<img src="../' + screenshot + '" alt="captured screenshot" />' if screenshot else '<div style="padding:80px">No screenshot captured.</div>'}
  <script id=\"pointspeak-overlays\" type=\"application/json\">{json.dumps(overlay_items)}</script>
</div>
<h2>Narration</h2>
<pre>{json.dumps(narrations, indent=2)}</pre>
<script>
const stage = document.querySelector('.stage');
const overlays = JSON.parse(document.getElementById('pointspeak-overlays').textContent);
for (const item of overlays) {{
  const s = item.shape || {{}};
  const div = document.createElement('div');
  div.className = `box ${{item.kind}}`;
  div.style.left = `${{s.x || 0}}px`;
  div.style.top = `${{s.y || 0}}px`;
  div.style.width = `${{Math.max(s.width || 1, 1)}}px`;
  div.style.height = `${{Math.max(s.height || 1, 1)}}px`;
  div.textContent = item.label || item.kind;
  stage.appendChild(div);
}}
</script>
"""
    replay_dir = root / "replay"
    replay_dir.mkdir(parents=True, exist_ok=True)
    replay_path = replay_dir / "index.html"
    replay_path.write_text(html, encoding="utf-8")
    return replay_path


def write_intake_artifacts(session_id: str, root: Path) -> dict[str, Any]:
    transcribe_missing_narrations(root)
    replay_path = write_replay_html(session_id, root)
    intake = build_action_draft(session_id, root)
    intake["artifacts"]["replayHtml"] = str(replay_path)
    privacy_path = root / "privacy-report.json"
    if privacy_path.exists():
        privacy = load_privacy_report(root)
        privacy["redactionsApplied"] = intake.get("redactionsApplied", [])
        write_json(privacy_path, privacy)
    handoff_dir = root / "handoff"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    write_json(handoff_dir / "intake.json", intake)
    (handoff_dir / "action-draft.md").write_text(render_action_draft(intake), encoding="utf-8")
    return intake


def render_handoff(session_id: str, root: Path, media: list[str]) -> str:
    page = load_page(root)
    elements = read_ndjson(root / "elements.ndjson")
    annotations = read_ndjson(root / "annotations.ndjson")
    narrations = read_ndjson(root / "narrations.ndjson")
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

    annotation_lines: list[str] = []
    for annotation in annotations:
        shape = annotation.get("shape") or {}
        shape_text = (
            f"x={shape.get('x')}, y={shape.get('y')}, w={shape.get('width')}, h={shape.get('height')} ({shape.get('coordinateSpace', 'viewport')})"
            if shape
            else "not captured"
        )
        targets = annotation.get("targetElementRefs") or []
        target_text = ", ".join(targets) if targets else "none"
        annotation_lines.append(f"- {annotation_label(annotation)}\n  - target elements: {target_text}\n  - shape: {shape_text}".rstrip())
    annotation_block = "\n".join(annotation_lines) if annotation_lines else "_None captured yet. Use annotation overlay after selecting an element._"

    narration_lines: list[str] = []
    for narration in narrations:
        audio = narration.get("audio") or "not captured"
        elements_target = ", ".join(narration.get("targetElementRefs") or []) or "none"
        annotations_target = ", ".join(narration.get("targetAnnotationRefs") or []) or "none"
        narration_lines.append(
            f"- {narration_label(narration)}\n  - audio: {root / audio if audio != 'not captured' else audio}\n  - target elements: {elements_target}\n  - target annotations: {annotations_target}".rstrip()
        )
    narration_block = "\n".join(narration_lines) if narration_lines else "_None captured yet. Narration starts in Milestone 5._"

    return f"""# PointSpeak Brief: {title}

## User Request
{build_action_draft(session_id, root).get('observedIntent')}

## Page
- URL: {page.get('url', '')}
- Title: {page.get('title', '')}
- Viewport: {viewport.get('width', '')}x{viewport.get('height', '')} @ {viewport.get('devicePixelRatio', '')}
- Scroll: {scroll.get('x', '')}, {scroll.get('y', '')}
- Captured At: {page.get('capturedAt', '')}

## Referenced Elements
{referenced_elements}

## Annotations
{annotation_block}

## Narration
{narration_block}

## Capture Points
{len(build_capture_points(elements, annotations, narrations))} point(s) captured. Multi-capture sessions are supported by appending more elements, annotations, and narrations to this bundle.

## Agent Intake
- Intake JSON: {root / 'handoff' / 'intake.json'}
- Action Draft: {root / 'handoff' / 'action-draft.md'}
- Replay: {root / 'replay' / 'index.html'}

## Artifacts
- Session ID: {session_id}
- Bundle: {root}
{screenshot_line}
- Manifest: {root / 'manifest.json'}
"""


def init_empty_bundle_files(root: Path) -> None:
    (root / "annotations.ndjson").write_text("", encoding="utf-8")
    (root / "elements.ndjson").write_text("", encoding="utf-8")
    (root / "narrations.ndjson").write_text("", encoding="utf-8")


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
        "narrations": "narrations.ndjson",
        "privacyReport": "privacy-report.json",
        "media": media,
        "handoff": "handoff/latest.md",
        "intake": "handoff/intake.json",
        "actionDraft": "handoff/action-draft.md",
        "replay": "replay/index.html",
        "desktopExport": "desktop/latest.json",
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
            "annotations": read_ndjson(root / "annotations.ndjson"),
            "narrations": read_ndjson(root / "narrations.ndjson"),
            "capturePoints": build_capture_points(read_ndjson(root / "elements.ndjson"), read_ndjson(root / "annotations.ndjson"), read_ndjson(root / "narrations.ndjson")),
        },
    )
    write_intake_artifacts(session_id, root)
    write_manifest(
        root,
        session_id=session_id,
        mode=str(manifest.get("mode", "snapshot")),
        source=str(manifest.get("source", "unknown")),
        media=media,
        created_at=str(manifest.get("createdAt") or utc_now()),
    )


def render_hermes_handoff_prompt(session_id: str, root: Path) -> str:
    handoff_path = root / "handoff" / "latest.md"
    handoff_text = handoff_path.read_text(encoding="utf-8") if handoff_path.exists() else ""
    manifest = load_manifest(root)
    media = list(manifest.get("media") or [])
    screenshot = root / media[0] if media else None
    return f"""PointSpeak visual briefing captured.

Use this as precise, local-first context for the current coding/UI task. Inspect the handoff markdown and, if useful, the screenshot artifact. The selected elements and annotations identify exactly what the user pointed at.

Session ID: {session_id}
Bundle path: {root}
Handoff markdown: {handoff_path}
Screenshot: {screenshot if screenshot else 'not captured'}

Handoff content:

{handoff_text}
"""


def submit_handoff_to_hermes(
    session_id: str,
    root: Path,
    req: SubmitHandoffRequest,
) -> SubmitHandoffResponse:
    hermes_api_url = (req.hermesApiUrl or DEFAULT_HERMES_API_URL).rstrip("/")
    model = req.model or DEFAULT_HERMES_MODEL
    handoff_path = root / "handoff" / "latest.md"
    request_path = root / "handoff" / "hermes-request.json"
    instructions = req.instructions or (
        "You are Coder receiving a PointSpeak visual briefing. Acknowledge the bundle, summarize the referenced UI "
        "element(s) and annotation(s), and propose the next concrete coding/debugging step. Do not modify files unless "
        "the user explicitly asks in a follow-up."
    )
    body = {
        "model": model,
        "session_id": f"pointspeak-{session_id}",
        "instructions": instructions,
        "input": render_hermes_handoff_prompt(session_id, root),
    }
    headers = {"Content-Type": "application/json", "X-Hermes-Session-Key": "pointspeak"}
    api_key = os.environ.get("POINTSPEAK_HERMES_API_KEY") or os.environ.get("API_SERVER_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    if req.dryRun:
        write_json(
            request_path,
            {
                "createdAt": utc_now(),
                "status": "dry_run",
                "hermesApiUrl": hermes_api_url,
                "endpoint": "/v1/runs",
                "headers": {key: ("<redacted>" if key.lower() == "authorization" else value) for key, value in headers.items()},
                "body": body,
            },
        )
        refresh_handoff_and_manifest(root, session_id)
        return SubmitHandoffResponse(
            sessionId=session_id,
            status="dry_run",
            hermesApiUrl=hermes_api_url,
            requestPath=str(request_path),
            handoff=str(handoff_path),
        )

    try:
        http_req = urllib.request.Request(
            f"{hermes_api_url}/v1/runs",
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(http_req, timeout=DEFAULT_HERMES_TIMEOUT_SECONDS) as response:
            response_body = json.loads(response.read().decode("utf-8") or "{}")
        run_id = response_body.get("run_id")
        write_json(
            request_path,
            {
                "createdAt": utc_now(),
                "status": "submitted",
                "hermesApiUrl": hermes_api_url,
                "endpoint": "/v1/runs",
                "runId": run_id,
                "response": response_body,
            },
        )
        append_ndjson(
            root / "timeline.ndjson",
            {
                "eventId": f"t_{uuid.uuid4().hex}",
                "timestampMs": 0,
                "type": "handoff.submitted",
                "data": {"target": "hermes", "runId": run_id, "hermesApiUrl": hermes_api_url},
            },
        )
        refresh_handoff_and_manifest(root, session_id)
        return SubmitHandoffResponse(
            sessionId=session_id,
            status="submitted",
            runId=run_id,
            hermesApiUrl=hermes_api_url,
            requestPath=str(request_path),
            handoff=str(handoff_path),
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        write_json(
            request_path,
            {
                "createdAt": utc_now(),
                "status": "failed",
                "hermesApiUrl": hermes_api_url,
                "endpoint": "/v1/runs",
                "error": str(exc),
                "body": body,
            },
        )
        refresh_handoff_and_manifest(root, session_id)
        return SubmitHandoffResponse(
            sessionId=session_id,
            status="failed",
            hermesApiUrl=hermes_api_url,
            requestPath=str(request_path),
            handoff=str(handoff_path),
            error=str(exc),
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
            "redactionControls": PrivacyControls().model_dump(mode="json"),
            "redactionsApplied": [],
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
        "annotations": read_ndjson(root / "annotations.ndjson"),
        "narrations": read_ndjson(root / "narrations.ndjson"),
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


@app.post("/sessions/{session_id}/annotations", response_model=AddAnnotationResponse)
def add_annotation(session_id: str, req: AddAnnotationRequest) -> AddAnnotationResponse:
    root = require_session_root(session_id)
    annotation_data = req.annotation.model_dump(mode="json", exclude_none=True)
    append_ndjson(root / "annotations.ndjson", annotation_data)
    append_ndjson(
        root / "timeline.ndjson",
        {
            "eventId": f"t_{uuid.uuid4().hex}",
            "timestampMs": req.annotation.timestampMs,
            "type": "annotation.created",
            "data": {
                "annotationId": req.annotation.annotationId,
                "targetElementRefs": req.annotation.targetElementRefs,
            },
        },
    )
    refresh_handoff_and_manifest(root, session_id)
    return AddAnnotationResponse(
        sessionId=session_id,
        annotationId=req.annotation.annotationId,
        annotationsPath=str(root / "annotations.ndjson"),
        handoff=str(root / "handoff" / "latest.md"),
    )


@app.post("/sessions/{session_id}/narrations", response_model=AddNarrationResponse)
def add_narration(session_id: str, req: AddNarrationRequest) -> AddNarrationResponse:
    root = require_session_root(session_id)
    narration_data = req.narration.model_dump(mode="json", exclude_none=True)
    audio_path: Path | None = None
    if req.narration.audioDataUrl:
        audio_bytes = decode_data_url(req.narration.audioDataUrl)
        extension = "webm"
        if "ogg" in req.narration.mimeType:
            extension = "ogg"
        elif "mpeg" in req.narration.mimeType or "mp3" in req.narration.mimeType:
            extension = "mp3"
        audio_path = root / "media" / f"{req.narration.narrationId}.{extension}"
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(audio_bytes)
        narration_data.pop("audioDataUrl", None)
        audio_rel = str(audio_path.relative_to(root))
        narration_data["audio"] = audio_rel
        narration_data["audioSha256"] = file_sha256(audio_path)
        narration_data["audioBytes"] = len(audio_bytes)
        manifest = load_manifest(root)
        media = list(manifest.get("media") or [])
        if audio_rel not in media:
            write_manifest(
                root,
                session_id=session_id,
                mode=str(manifest.get("mode", "snapshot")),
                source=str(manifest.get("source", "unknown")),
                media=[*media, audio_rel],
                created_at=str(manifest.get("createdAt") or utc_now()),
            )
        privacy_path = root / "privacy-report.json"
        if privacy_path.exists():
            privacy = json.loads(privacy_path.read_text(encoding="utf-8"))
            defaults = privacy.setdefault("defaults", {})
            defaults["audioCaptured"] = True
            write_json(privacy_path, privacy)

    append_ndjson(root / "narrations.ndjson", narration_data)
    append_ndjson(
        root / "timeline.ndjson",
        {
            "eventId": f"t_{uuid.uuid4().hex}",
            "timestampMs": req.narration.timestampMs,
            "type": "narration.captured",
            "media": narration_data.get("audio"),
            "data": {
                "narrationId": req.narration.narrationId,
                "targetElementRefs": req.narration.targetElementRefs,
                "targetAnnotationRefs": req.narration.targetAnnotationRefs,
                "durationMs": req.narration.durationMs,
            },
        },
    )
    refresh_handoff_and_manifest(root, session_id)
    return AddNarrationResponse(
        sessionId=session_id,
        narrationId=req.narration.narrationId,
        audioPath=str(audio_path) if audio_path else None,
        narrationsPath=str(root / "narrations.ndjson"),
        handoff=str(root / "handoff" / "latest.md"),
    )


@app.post("/sessions/{session_id}/handoff", response_model=SubmitHandoffResponse)
def submit_handoff(session_id: str, req: SubmitHandoffRequest | None = None) -> SubmitHandoffResponse:
    root = require_session_root(session_id)
    refresh_handoff_and_manifest(root, session_id)
    return submit_handoff_to_hermes(session_id, root, req or SubmitHandoffRequest())


@app.post("/bridge/activate")
def activate_bridge(req: BridgeActivateRequest) -> dict[str, object]:
    expires = datetime.now(timezone.utc).timestamp() + req.ttlMinutes * 60
    expires_at = datetime.fromtimestamp(expires, timezone.utc).isoformat()
    lease = {
        "agent": normalize_target(req.agent),
        "activatedAt": utc_now(),
        "expiresAt": expires_at,
        "ttlMinutes": req.ttlMinutes,
        "hermesApiUrl": req.hermesApiUrl,
        "apiKeyEnv": req.apiKeyEnv,
        "model": req.model,
        "notifyTarget": req.notifyTarget,
        "wakeChat": req.wakeChat,
        "includeBacklogMinutes": req.includeBacklogMinutes,
    }
    state = {"activeLease": lease, "updatedAt": utc_now()}
    write_json(bridge_state_path(), state)
    backlog: list[dict[str, Any]] = []
    if req.includeBacklogMinutes:
        cutoff = datetime.now(timezone.utc).timestamp() - req.includeBacklogMinutes * 60
        for event in read_bridge_events(target="unclaimed", status="queued", limit=500):
            created = parse_utc(event.get("createdAt"))
            if created and created.timestamp() >= cutoff:
                backlog.append(event)
    return {"activeLease": lease, "backlog": backlog, "bridgeRoot": str(bridge_dir())}


@app.post("/bridge/release")
def release_bridge(req: BridgeReleaseRequest | None = None) -> dict[str, object]:
    state = load_bridge_state()
    lease = active_bridge_lease()
    if req and req.agent and lease and lease.get("agent") != normalize_target(req.agent):
        return {"released": False, "activeLease": lease}
    state["activeLease"] = None
    state["updatedAt"] = utc_now()
    write_json(bridge_state_path(), state)
    return {"released": True, "activeLease": None}


@app.get("/bridge/status")
def bridge_status() -> dict[str, object]:
    lease = active_bridge_lease()
    return {
        "activeLease": lease,
        "bridgeRoot": str(bridge_dir()),
        "recent": read_bridge_events(limit=10),
        "queued": {
            "unclaimed": len(read_bridge_events(target="unclaimed", status="queued", limit=1000)),
            **({lease["agent"]: len(read_bridge_events(target=lease["agent"], status="queued", limit=1000))} if lease else {}),
        },
    }


@app.get("/bridge/inbox")
def bridge_inbox(target: str | None = None, status: str | None = "queued", limit: int = 50) -> dict[str, object]:
    return {"target": normalize_target(target), "events": read_bridge_events(target=target, status=status, limit=limit)}


@app.post("/bridge/queue", response_model=BridgeEventResponse)
def bridge_queue(req: BridgeQueueRequest) -> BridgeEventResponse:
    root = require_session_root(req.sessionId)
    refresh_handoff_and_manifest(root, req.sessionId)
    event = queue_bridge_session(req.sessionId, root, req.target)
    refresh_handoff_and_manifest(root, req.sessionId)
    return bridge_response_from_event(event, active_bridge_lease())


@app.post("/bridge/claim")
def bridge_claim(target: str, agent: str | None = None, limit: int = 10) -> dict[str, object]:
    # Append-only claim log: return matching events and record claim events without mutating historical rows.
    claimant = normalize_target(agent or target)
    events = read_bridge_events(target=target, status="queued", limit=limit)
    claimed = []
    for event in events:
        claim = dict(event)
        claim["eventId"] = f"evt_{uuid.uuid4().hex}"
        claim["createdAt"] = utc_now()
        claim["status"] = "claimed"
        claim["claimedBy"] = claimant
        claim["claimedAt"] = utc_now()
        append_bridge_event(claim)
        claimed.append(claim)
    return {"claimedBy": claimant, "events": claimed}


@app.post("/sessions/{session_id}/bridge-finalize", response_model=BridgeFinalizeResponse)
def bridge_finalize(session_id: str) -> BridgeFinalizeResponse:
    root = require_session_root(session_id)
    refresh_handoff_and_manifest(root, session_id)
    intake_data = write_intake_artifacts(session_id, root)
    intake = IntakeResponse(
        sessionId=session_id,
        intakePath=str(root / "handoff" / "intake.json"),
        actionDraftPath=str(root / "handoff" / "action-draft.md"),
        replayPath=str(root / "replay" / "index.html"),
        summary=str(intake_data.get("summary", "")),
        suggestedActions=list(intake_data.get("suggestedActions") or []),
        redactionsApplied=list(intake_data.get("redactionsApplied") or []),
    )
    desktop = export_desktop_context(session_id)
    lease = active_bridge_lease()
    handoff: SubmitHandoffResponse | None = None
    if lease and lease.get("hermesApiUrl"):
        env_key = str(lease.get("apiKeyEnv") or "").strip()
        previous = os.environ.get("POINTSPEAK_HERMES_API_KEY")
        if env_key and os.environ.get(env_key):
            os.environ["POINTSPEAK_HERMES_API_KEY"] = str(os.environ[env_key])
        try:
            handoff = submit_handoff_to_hermes(
                session_id,
                root,
                SubmitHandoffRequest(
                    hermesApiUrl=str(lease.get("hermesApiUrl")),
                    model=lease.get("model") or DEFAULT_HERMES_MODEL,
                    instructions=bridge_wake_instructions(lease) if lease.get("wakeChat", True) else None,
                ),
            )
        finally:
            if previous is None:
                os.environ.pop("POINTSPEAK_HERMES_API_KEY", None)
            else:
                os.environ["POINTSPEAK_HERMES_API_KEY"] = previous
    else:
        # Still write a dry-run request so the package is self-describing, but do not treat no live agent as an error.
        handoff = submit_handoff_to_hermes(session_id, root, SubmitHandoffRequest(dryRun=True))
    event = queue_bridge_session(session_id, root, delivery=handoff)
    refresh_handoff_and_manifest(root, session_id)
    return BridgeFinalizeResponse(sessionId=session_id, bridge=bridge_response_from_event(event, lease), intake=intake, desktop=desktop, handoff=handoff)


@app.post("/sessions/{session_id}/privacy")
def update_privacy_controls(session_id: str, req: UpdatePrivacyControlsRequest) -> dict[str, object]:
    root = require_session_root(session_id)
    privacy = load_privacy_report(root)
    privacy["redactionControls"] = req.controls.model_dump(mode="json")
    privacy.setdefault("redactionsApplied", [])
    write_json(root / "privacy-report.json", privacy)
    refresh_handoff_and_manifest(root, session_id)
    return {"sessionId": session_id, "privacyReport": str(root / "privacy-report.json"), "controls": privacy["redactionControls"]}


@app.post("/sessions/{session_id}/intake", response_model=IntakeResponse)
def create_intake(session_id: str) -> IntakeResponse:
    root = require_session_root(session_id)
    refresh_handoff_and_manifest(root, session_id)
    intake = write_intake_artifacts(session_id, root)
    return IntakeResponse(
        sessionId=session_id,
        intakePath=str(root / "handoff" / "intake.json"),
        actionDraftPath=str(root / "handoff" / "action-draft.md"),
        replayPath=str(root / "replay" / "index.html"),
        summary=str(intake.get("summary", "")),
        suggestedActions=list(intake.get("suggestedActions") or []),
        redactionsApplied=list(intake.get("redactionsApplied") or []),
    )


@app.get("/sessions/{session_id}/replay", response_model=ReplayResponse)
def create_replay(session_id: str) -> ReplayResponse:
    root = require_session_root(session_id)
    replay_path = write_replay_html(session_id, root)
    refresh_handoff_and_manifest(root, session_id)
    return ReplayResponse(sessionId=session_id, replayPath=str(replay_path))


@app.get("/sessions/{session_id}/capture-points")
def get_capture_points(session_id: str) -> dict[str, object]:
    root = require_session_root(session_id)
    page, elements, annotations, narrations, redactions = sanitized_records(root)
    return {
        "sessionId": session_id,
        "page": page,
        "capturePoints": build_capture_points(elements, annotations, narrations),
        "redactionsApplied": redactions,
    }


@app.post("/sessions/{session_id}/desktop-export", response_model=DesktopExportResponse)
def export_desktop_context(session_id: str) -> DesktopExportResponse:
    root = require_session_root(session_id)
    refresh_handoff_and_manifest(root, session_id)
    intake = write_intake_artifacts(session_id, root)
    DEFAULT_DESKTOP_INBOX.mkdir(parents=True, exist_ok=True)
    export_path = DEFAULT_DESKTOP_INBOX / f"{session_id}.json"
    write_json(
        export_path,
        {
            "schemaVersion": SCHEMA_VERSION,
            "source": "pointspeak",
            "createdAt": utc_now(),
            "sessionId": session_id,
            "bundlePath": str(root),
            "intake": intake,
        },
    )
    desktop_dir = root / "desktop"
    desktop_dir.mkdir(parents=True, exist_ok=True)
    write_json(desktop_dir / "latest.json", {"exportPath": str(export_path), "desktopInbox": str(DEFAULT_DESKTOP_INBOX)})
    refresh_handoff_and_manifest(root, session_id)
    return DesktopExportResponse(sessionId=session_id, exportPath=str(export_path), desktopInbox=str(DEFAULT_DESKTOP_INBOX))


@app.get("/sessions/{session_id}/handoff.md", response_class=PlainTextResponse)
def get_handoff(session_id: str) -> str:
    handoff_path = require_session_root(session_id) / "handoff" / "latest.md"
    if not handoff_path.exists():
        raise HTTPException(status_code=404, detail="Handoff not found")
    return handoff_path.read_text(encoding="utf-8")


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=48321)
