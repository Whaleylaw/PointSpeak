# PointSpeak

Agent-ready visual briefings for coding agents.

PointSpeak captures screenshots, annotations, DOM/element metadata, and later narrated walkthroughs so a user can point at an interface, explain what they mean, and send precise implementation context to an agent.

## Current Status

Milestones 6-10 are implemented: Hermes intake, replay, desktop export, privacy/redaction controls, and multi-capture sessions are now available:

- `apps/extension` — Chrome MV3 extension that captures the active visible tab, starts element-pick mode, captures annotations, optionally records short narrations, supports adding more capture points to the same session, and finalizes the Hermes/RoscoeDesktop handoff.
- `apps/receiver` — local FastAPI receiver that writes `.pointspeak` bundles, stores narration audio/transcripts, generates Hermes intake/action drafts, writes browser replay HTML, exports RoscoeDesktop inbox payloads, and can submit them to Hermes API Server.
- `packages/schema` — shared TypeScript schema definitions.
- `packages/annotator` — annotation helper types.
- `packages/capture-core` — placeholder capture/event helpers.
- `packages/handoff` — handoff markdown helper.
- `docs/` — architecture, privacy, and bundle-format notes.

## Quick Start

Install/build the TypeScript workspaces:

```bash
npm install
npm run build
```

Install/start the receiver:

```bash
cd apps/receiver
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pointspeak-receiver
```

Then load `apps/extension/dist` as an unpacked Chrome extension. Clicking the PointSpeak toolbar button captures the active tab screenshot and page metadata, prompts you to click a page element, lets you drag an annotation rectangle and enter a short note, then offers an optional short voice narration. After each point you can add another point to the same session or finalize. The bundle is written into:

```text
~/.pointspeak/sessions/<session>/session.pointspeak/
```

Smoke-test the receiver without Chrome:

```bash
cd apps/receiver
source .venv/bin/activate
pointspeak-receiver-smoke
```

## Hermes handoff

After annotation and optional narration are saved, the extension asks the receiver to submit the bundle to Hermes API Server:

```text
POST http://127.0.0.1:48321/sessions/<session_id>/handoff
```

The receiver sends a non-blocking run request to Hermes:

```text
POST http://127.0.0.1:8642/v1/runs
```

Configuration:

- `POINTSPEAK_HERMES_API_URL` — defaults to `http://127.0.0.1:8642`
- `POINTSPEAK_HERMES_MODEL` — defaults to `hermes-agent`
- `POINTSPEAK_HERMES_API_KEY` or `API_SERVER_KEY` — optional bearer token if Hermes API Server requires auth
- `POINTSPEAK_HERMES_TIMEOUT_SECONDS` — defaults to `3`

Every attempt writes:

```text
handoff/hermes-request.json
```


## Milestones 6-10

The receiver now derives agent-ready artifacts from each bundle:

- **Milestone 6 — Hermes Intake:** `POST /sessions/<id>/intake` writes `handoff/intake.json` and `handoff/action-draft.md`, including observed intent, capture points, redaction notes, artifact paths, and suggested next actions.
- **Milestone 7 — Browser Replay:** `GET /sessions/<id>/replay` writes `replay/index.html`, a local screenshot viewer with element, annotation, and redaction overlays.
- **Milestone 8 — RoscoeDesktop Export:** `POST /sessions/<id>/desktop-export` writes a desktop inbox payload to `POINTSPEAK_DESKTOP_INBOX` or `~/Github/RoscoeDesktop/.pointspeak-inbox`.
- **Milestone 9 — Privacy Controls:** `POST /sessions/<id>/privacy` stores text redaction controls and screenshot mask regions in `privacy-report.json`; intake/replay generation applies those controls to shared text and overlays.
- **Milestone 10 — Multi-capture Sessions:** sessions can contain multiple element/annotation/narration groups, exposed as `capturePoints` in `handoff/latest.json`, `handoff/intake.json`, and `GET /sessions/<id>/capture-points`.

Finalized bundles include:

```text
handoff/latest.md
handoff/latest.json
handoff/intake.json
handoff/action-draft.md
replay/index.html
desktop/latest.json
privacy-report.json
```
