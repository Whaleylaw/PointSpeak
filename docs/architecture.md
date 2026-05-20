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

## Milestone 2 Implementation

The current implementation also supports element selection:

- After snapshot capture, the extension asks the content script to enter element-pick mode.
- The content script displays a small instruction pill and hover rectangle.
- Clicking an element extracts role/name/text/tag/bounding box, selector alternatives, DOM path, and a state hash.
- The background service worker posts that element to `POST /sessions/{session_id}/elements`.
- Receiver appends the element to `elements.ndjson`, appends an `element.selected` timeline event, refreshes handoff files, and rewrites manifest hashes.

## Milestone 4 Implementation

Hermes/Coder handoff is now wired through the local receiver:

- After annotation capture, the extension calls `POST /sessions/{session_id}/handoff`.
- The receiver renders a self-contained handoff prompt with bundle path, handoff markdown path, screenshot path, referenced elements, and annotations.
- The receiver submits a non-blocking run to Hermes API Server at `/v1/runs`.
- Each handoff attempt is written to `handoff/hermes-request.json` and included in manifest hashes.
- If Hermes API Server is unavailable, the bundle remains valid locally and the failed handoff attempt is recorded for retry.

## Design Principles

- Screenshot is the visual source of truth.
- DOM/ARIA metadata adds semantic precision but is best-effort.
- Bundles are local-first and durable.
- Privacy masking is default-on for sensitive fields.
- Video/live modes are future extensions, not MVP requirements.
