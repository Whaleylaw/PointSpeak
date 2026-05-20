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

        element_result = main.add_element(
            result.sessionId,
            main.AddElementRequest(
                element=main.ElementRef(
                    elementRef="e_smoke",
                    timestampMs=0,
                    url="http://localhost:5173/smoke",
                    role="button",
                    name="Smoke Button",
                    text="Smoke Button",
                    tagName="button",
                    boundingBox=main.BoundingBox(x=10, y=20, width=100, height=40),
                    selectors=[main.Selector(type="aria", value='button[name="Smoke Button"]', confidence=0.9)],
                    domPath="html > body > button",
                    stateHash="smoke-state",
                )
            ),
        )
        if element_result.elementRef != "e_smoke":
            raise AssertionError(f"Unexpected element response: {element_result}")
        elements_text = (bundle / "elements.ndjson").read_text()
        if "e_smoke" not in elements_text:
            raise AssertionError("Element not appended")
        handoff = (bundle / "handoff" / "latest.md").read_text()
        if "Smoke Button" not in handoff:
            raise AssertionError("Handoff did not include selected element")

        annotation_result = main.add_annotation(
            result.sessionId,
            main.AddAnnotationRequest(
                annotation=main.Annotation(
                    annotationId="a_smoke",
                    type="rectangle",
                    timestampMs=0,
                    text="Look at this smoke-test rectangle",
                    targetElementRefs=["e_smoke"],
                    color="#f97316",
                    shape=main.AnnotationShape(
                        x=12,
                        y=24,
                        width=80,
                        height=32,
                        pageX=12,
                        pageY=144,
                        coordinateSpace="viewport",
                    ),
                )
            ),
        )
        if annotation_result.annotationId != "a_smoke":
            raise AssertionError(f"Unexpected annotation response: {annotation_result}")
        annotations_text = (bundle / "annotations.ndjson").read_text()
        if "a_smoke" not in annotations_text:
            raise AssertionError("Annotation not appended")
        handoff = (bundle / "handoff" / "latest.md").read_text()
        if "Look at this smoke-test rectangle" not in handoff or "e_smoke" not in handoff:
            raise AssertionError("Handoff did not include annotation linked to element")

        handoff_result = main.submit_handoff(
            result.sessionId,
            main.SubmitHandoffRequest(dryRun=True, hermesApiUrl="http://127.0.0.1:8642"),
        )
        if handoff_result.status != "dry_run":
            raise AssertionError(f"Unexpected handoff response: {handoff_result}")
        request_path = Path(handoff_result.requestPath)
        if not request_path.exists():
            raise AssertionError("Hermes handoff request file not written")
        request_json = json.loads(request_path.read_text())
        if result.sessionId not in request_json["body"]["input"] or "PointSpeak visual briefing captured" not in request_json["body"]["input"]:
            raise AssertionError("Hermes handoff prompt missing PointSpeak context")

        print("receiver smoke ok")
        print(result.model_dump())
        print(element_result.model_dump())
        print(annotation_result.model_dump())
        print(handoff_result.model_dump())


if __name__ == "__main__":
    run()
