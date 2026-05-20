# PointSpeak Architecture

PointSpeak is split into a browser capture client, local receiver, shared schemas, and handoff generation.

## MVP Flow

1. Chrome extension captures visible tab screenshot.
2. Content script gathers page and selected element metadata.
3. User adds annotations/notes.
4. Extension posts session data to local receiver.
5. Receiver writes a durable bundle and generates agent handoff files.
6. Receiver can notify Hermes/Coder with the bundle path.

## Design Principles

- Screenshot is the visual source of truth.
- DOM/ARIA metadata adds semantic precision but is best-effort.
- Bundles are local-first and durable.
- Privacy masking is default-on for sensitive fields.
- Video/live modes are future extensions, not MVP requirements.
