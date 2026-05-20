# PointSpeak

Agent-ready visual briefings for coding agents.

PointSpeak captures screenshots, annotations, DOM/element metadata, and later narrated walkthroughs so a user can point at an interface, explain what they mean, and send precise implementation context to an agent.

## Current Status

Milestone 4 Hermes handoff is implemented:

- `apps/extension` — Chrome MV3 extension that captures the active visible tab, starts element-pick mode, captures an annotation, and submits a Hermes handoff.
- `apps/receiver` — local FastAPI receiver that writes `.pointspeak` bundles and can submit them to Hermes API Server.
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

Then load `apps/extension/dist` as an unpacked Chrome extension. Clicking the PointSpeak toolbar button captures the active tab screenshot and page metadata, prompts you to click a page element, then lets you drag an annotation rectangle and enter a short note. The bundle is written into:

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

After an annotation is saved, the extension asks the receiver to submit the bundle to Hermes API Server:

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
