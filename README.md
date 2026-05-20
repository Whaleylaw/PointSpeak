# PointSpeak

Agent-ready visual briefings for coding agents.

PointSpeak captures screenshots, annotations, DOM/element metadata, and later narrated walkthroughs so a user can point at an interface, explain what they mean, and send precise implementation context to an agent.

## Milestone 0 Status

This repository currently contains the initial monorepo skeleton:

- `apps/extension` — Chrome MV3 extension skeleton.
- `apps/receiver` — local FastAPI receiver skeleton.
- `packages/schema` — shared TypeScript schema definitions.
- `packages/annotator` — placeholder annotation package.
- `packages/capture-core` — placeholder capture/event helpers.
- `packages/handoff` — placeholder handoff generation helpers.
- `docs/` — architecture, privacy, and bundle-format notes.

## Quick Start

```bash
npm install
npm run build

cd apps/receiver
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn pointspeak_receiver.main:app --reload --host 127.0.0.1 --port 48321
```

Then load `apps/extension/dist` as an unpacked Chrome extension after `npm run build`.
