# PointSpeak

Agent-ready visual briefings for coding agents.

PointSpeak captures screenshots, annotations, DOM/element metadata, and later narrated walkthroughs so a user can point at an interface, explain what they mean, and send precise implementation context to an agent.

## Current Status

Milestone 1 snapshot capture is implemented:

- `apps/extension` — Chrome MV3 extension that captures the active visible tab.
- `apps/receiver` — local FastAPI receiver that writes `.pointspeak` bundles.
- `packages/schema` — shared TypeScript schema definitions.
- `packages/annotator` — placeholder annotation package.
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

Then load `apps/extension/dist` as an unpacked Chrome extension. Clicking the PointSpeak toolbar button captures the active tab screenshot and page metadata into:

```text
~/.pointspeak/sessions/<session>/session.pointspeak/
```

Smoke-test the receiver without Chrome:

```bash
cd apps/receiver
source .venv/bin/activate
pointspeak-receiver-smoke
```
