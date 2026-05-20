# PointSpeak Bundle Format

MVP bundle layout:

```text
session.pointspeak/
  manifest.json
  timeline.ndjson
  annotations.ndjson
  page.json
  elements.ndjson
  privacy-report.json
  media/
    screenshot.png
  handoff/
    latest.md
    latest.json
```

Milestone 1 writes `manifest.json` last, after all other files, so its `hashes` object can include SHA-256 hashes for the bundle files that already exist. The screenshot hash is also written as `visualHash` in `timeline.ndjson`.

Milestone 2 appends selected elements to `elements.ndjson` and appends `element.selected` events to `timeline.ndjson`. Handoff files and manifest hashes are refreshed after each element append.

Future additions may include transcripts, conversation state, retrieval logs, suggestions, video, keyframes, console/network logs, and an offline viewer.
