# PointSpeak Architecture

PointSpeak is split into a browser capture client, local receiver, shared schemas, and handoff generation.

## MVP Flow

1. Chrome extension captures visible tab screenshot.
2. Content script gathers page and selected element metadata.
3. User adds annotations/notes.
4. Extension posts session data to local receiver.
5. Receiver writes a durable bundle and generates agent handoff files.
6. Receiver can notify Hermes/Coder with the bundle path.

## Milestone 1 Implementation

The current implementation supports snapshot capture:

- Chrome extension toolbar action captures the visible active tab.
- Extension reads URL/title/viewport/scroll metadata from the active tab.
- Extension posts screenshot and page metadata to `POST /sessions` on the local receiver.
- Receiver writes the bundle directory, screenshot, page metadata, timeline, privacy report, handoff files, and manifest with SHA-256 file hashes.
- Receiver exposes `GET /sessions/{session_id}` and `GET /sessions/{session_id}/handoff.md`.

## Design Principles

- Screenshot is the visual source of truth.
- DOM/ARIA metadata adds semantic precision but is best-effort.
- Bundles are local-first and durable.
- Privacy masking is default-on for sensitive fields.
- Video/live modes are future extensions, not MVP requirements.
