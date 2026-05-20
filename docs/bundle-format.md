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

Future additions may include transcripts, conversation state, retrieval logs, suggestions, video, keyframes, console/network logs, and an offline viewer.
