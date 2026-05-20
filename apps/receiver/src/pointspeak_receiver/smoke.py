from __future__ import annotations

import base64
import json
import tempfile
from pathlib import Path

from pointspeak_receiver import main
from pointspeak_receiver.main import CreateSessionRequest, PageMetadata, Scroll, Viewport

# A valid 1x1 transparent PNG.
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def run() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        main.DEFAULT_STORAGE_ROOT = Path(tmp)
        req = CreateSessionRequest(
            mode="snapshot",
            source="receiver-smoke",
            page=PageMetadata(
                url="http://localhost:5173/smoke",
                title="PointSpeak Smoke",
                viewport=Viewport(width=1200, height=800, devicePixelRatio=2),
                scroll=Scroll(x=0, y=120),
                capturedAt="2026-05-20T00:00:00Z",
            ),
            screenshotDataUrl="data:image/png;base64," + base64.b64encode(PNG_1X1).decode("ascii"),
        )
        result = main.create_session(req)
        bundle = Path(result.bundlePath)

        required = [
            "manifest.json",
            "page.json",
            "timeline.ndjson",
            "annotations.ndjson",
            "elements.ndjson",
            "privacy-report.json",
            "media/screenshot.png",
            "handoff/latest.md",
            "handoff/latest.json",
        ]
        missing = [rel for rel in required if not (bundle / rel).exists()]
        if missing:
            raise AssertionError(f"Missing bundle files: {missing}")

        manifest = json.loads((bundle / "manifest.json").read_text())
        if manifest["media"] != ["media/screenshot.png"]:
            raise AssertionError(f"Unexpected media list: {manifest['media']}")
        if "media/screenshot.png" not in manifest["hashes"]:
            raise AssertionError("Missing screenshot hash")
        timeline = (bundle / "timeline.ndjson").read_text().strip()
        if "snapshot.captured" not in timeline or "visualHash" not in timeline:
            raise AssertionError(f"Unexpected timeline: {timeline}")

        print("receiver smoke ok")
        print(result.model_dump())


if __name__ == "__main__":
    run()
