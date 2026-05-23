# PointSpeak

PointSpeak is a local-first context capture tool for giving coding agents precise visual context from a browser page. It captures screenshots, DOM metadata, selected elements, drawn annotations, typed notes, and optional voice narration, then packages that context into a portable bundle an agent can inspect or receive through a local bridge.

The goal is simple: instead of trying to describe “that button over there” in a chat box, point at it, mark it up, explain what you mean, and send the agent a reproducible visual briefing.

## What it does

- Captures the visible browser tab as a screenshot.
- Lets you pick a target DOM element and records useful metadata such as selectors, text snippets, bounds, and accessibility labels.
- Lets you draw annotation rectangles and add notes.
- Supports multi-point capture sessions, so one briefing can include several related UI observations.
- Records optional voice narration, with local speech-to-text support when `faster-whisper` is installed.
- Writes durable local `.pointspeak` bundles that can be inspected, archived, or sent to an agent.
- Generates agent-friendly handoff artifacts, including Markdown summaries, JSON intake, privacy reports, and a local replay page.
- Provides a bridge router for delivering finalized captures to a local Hermes-compatible agent server.

## Repository layout

```text
apps/
  extension/   Chrome MV3 extension for capture, annotation, narration, and session finalization
  receiver/    Local FastAPI receiver that stores bundles and creates handoff artifacts
packages/
  schema/      Shared TypeScript schemas
  annotator/   Annotation helper types
  capture-core/ Core capture/event helpers
  handoff/     Handoff rendering helpers
docs/          Architecture and bundle-format notes
```

## Quick start

### 1. Install and build the browser extension

PointSpeak uses Node 22+.

```bash
npm install
npm run build
```

This builds the extension into:

```text
apps/extension/dist
```

Load that directory in Chrome or a Chromium-based browser:

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Click **Load unpacked**.
4. Select `apps/extension/dist`.

### 2. Start the local receiver

```bash
cd apps/receiver
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pointspeak-receiver
```

By default the receiver listens on:

```text
http://127.0.0.1:48321
```

### 3. Capture a page

Click the PointSpeak extension button, then:

1. Select the relevant page element.
2. Draw an annotation if helpful.
3. Add a short typed note.
4. Optionally record narration.
5. Add another capture point or finalize the session.

Finalized sessions are written under:

```text
~/.pointspeak/sessions/<session-id>/session.pointspeak/
```

## Bundle contents

A finalized bundle is a normal folder on disk. Typical generated artifacts include:

```text
captures.ndjson
annotations.ndjson
elements.ndjson
narrations.ndjson
privacy-report.json
handoff/latest.md
handoff/latest.json
handoff/intake.json
handoff/action-draft.md
replay/index.html
desktop/latest.json
```

Useful files:

- `handoff/latest.md` — a human- and agent-readable summary of the capture.
- `handoff/intake.json` — structured capture points, suggested actions, redaction status, and artifact paths.
- `replay/index.html` — a local replay viewer with screenshot and annotation overlays.
- `privacy-report.json` — redaction controls and privacy metadata.

## Local speech-to-text

Voice narration is optional. Capture works even when speech-to-text is not installed.

For local transcription, install `faster-whisper` in the receiver environment:

```bash
cd apps/receiver
source .venv/bin/activate
pip install faster-whisper
export POINTSPEAK_STT_ENABLED=true
export POINTSPEAK_STT_MODEL=base   # optional; defaults to base
pointspeak-receiver
```

## Agent bridge

PointSpeak separates local capture from agent delivery:

- Local capture is durable and should succeed even when no agent is available.
- Agent delivery is optional and lease-based.
- If delivery fails, the bundle remains available locally and can be retried or inspected manually.

The receiver exposes bridge endpoints:

```text
POST /bridge/activate
POST /bridge/release
GET  /bridge/status
GET  /bridge/inbox
POST /bridge/claim
POST /bridge/queue
POST /sessions/<id>/bridge-finalize
```

Example bridge activation:

```json
{
  "agent": "coder",
  "ttlMinutes": 120,
  "hermesApiUrl": "http://127.0.0.1:8642",
  "apiKeyEnv": "POINTSPEAK_HERMES_API_KEY",
  "notifyTarget": "telegram",
  "wakeChat": true,
  "bridgeMode": "api_run"
}
```

Supported bridge modes:

- `api_run` — submits the handoff to a Hermes-compatible `/v1/runs` API.
- `native_telegram` — when used with a compatible Hermes Gateway, injects the handoff into the live Telegram gateway session so the agent processes it like a normal chat message.

Configuration variables:

```text
POINTSPEAK_HERMES_API_URL          Default Hermes-compatible API URL
POINTSPEAK_HERMES_API_KEY          Bearer token for the agent API, if required
POINTSPEAK_HERMES_MODEL            Optional model name for API-run handoff
POINTSPEAK_HERMES_TIMEOUT_SECONDS  Request timeout for handoff submission
POINTSPEAK_STT_ENABLED             Enable best-effort local narration transcription
POINTSPEAK_STT_MODEL               faster-whisper model name; defaults to base
POINTSPEAK_ROOT                    Override the default ~/.pointspeak storage root
```

## Receiver smoke test

Run the receiver smoke test without Chrome:

```bash
cd apps/receiver
source .venv/bin/activate
pointspeak-receiver-smoke
```

Or from the repository root:

```bash
PYTHONPATH=apps/receiver/src python -m pointspeak_receiver.smoke
```

## Development

Common commands:

```bash
npm run typecheck
npm run build
```

The extension build output and local receiver data are intentionally ignored by Git. Do not commit `.env` files, local `.pointspeak` bundles, virtual environments, `node_modules`, or generated `dist` folders.

## Privacy model

PointSpeak is designed to be local-first:

- Captures are stored on your machine by default.
- Redaction controls are stored with the bundle.
- Generated handoffs should reference local artifact paths rather than uploading screenshots by default.
- Agent delivery is explicit and configurable.

You should still review bundles before sharing them outside your own trusted environment, especially when capturing pages that may contain secrets, client data, or personal information.

## License

No license has been selected yet. Until a license is added, all rights are reserved by the repository owner.
