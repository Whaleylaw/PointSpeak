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
            "narrations.ndjson",
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

        narration_result = main.add_narration(
            result.sessionId,
            main.AddNarrationRequest(
                narration=main.Narration(
                    narrationId="n_smoke",
                    timestampMs=0,
                    durationMs=1500,
                    transcript="This is the narrated smoke-test context.",
                    audioDataUrl="data:audio/webm;base64," + base64.b64encode(b"smoke-audio").decode("ascii"),
                    mimeType="audio/webm",
                    targetElementRefs=["e_smoke"],
                    targetAnnotationRefs=["a_smoke"],
                )
            ),
        )
        if narration_result.narrationId != "n_smoke":
            raise AssertionError(f"Unexpected narration response: {narration_result}")
        if not narration_result.audioPath or not Path(narration_result.audioPath).exists():
            raise AssertionError("Narration audio file not written")
        narrations_text = (bundle / "narrations.ndjson").read_text()
        if "n_smoke" not in narrations_text or "audioDataUrl" in narrations_text:
            raise AssertionError("Narration not appended cleanly")
        handoff = (bundle / "handoff" / "latest.md").read_text()
        if "This is the narrated smoke-test context" not in handoff:
            raise AssertionError("Handoff did not include narration transcript")

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

        # Milestones 6-10: privacy controls, intake/action draft, replay, desktop export, and multi-capture points.
        privacy_result = main.update_privacy_controls(
            result.sessionId,
            main.UpdatePrivacyControlsRequest(
                controls=main.PrivacyControls(
                    screenshotRegions=[
                        main.RedactionRegion(
                            redactionId="r_smoke",
                            reason="hide account number",
                            shape=main.AnnotationShape(x=1, y=1, width=12, height=12, coordinateSpace="viewport"),
                        )
                    ]
                )
            ),
        )
        if "r_smoke" not in json.dumps(privacy_result):
            raise AssertionError("Privacy controls did not persist")

        second_element_result = main.add_element(
            result.sessionId,
            main.AddElementRequest(
                element=main.ElementRef(
                    elementRef="e_smoke_two",
                    timestampMs=0,
                    url="http://localhost:5173/smoke",
                    role="link",
                    name="Second Smoke Target",
                    text="Second Smoke Target",
                    tagName="a",
                    boundingBox=main.BoundingBox(x=140, y=20, width=120, height=30),
                    selectors=[main.Selector(type="text", value="Second Smoke Target", confidence=0.5)],
                )
            ),
        )
        if second_element_result.elementRef != "e_smoke_two":
            raise AssertionError("Second capture point element failed")

        intake = main.create_intake(result.sessionId)
        if not Path(intake.intakePath).exists() or not Path(intake.actionDraftPath).exists():
            raise AssertionError("Intake artifacts not written")
        if "PointSpeak capture" not in intake.summary or not intake.suggestedActions:
            raise AssertionError(f"Unexpected intake summary: {intake}")

        replay = main.create_replay(result.sessionId)
        if not Path(replay.replayPath).exists() or "pointspeak-overlays" not in Path(replay.replayPath).read_text():
            raise AssertionError("Replay HTML not written")

        points = main.get_capture_points(result.sessionId)
        if len(points["capturePoints"]) < 2:
            raise AssertionError(f"Expected multi-capture points, got {points}")

        desktop = main.export_desktop_context(result.sessionId)
        if not Path(desktop.exportPath).exists():
            raise AssertionError("Desktop export not written")

        print("receiver smoke ok")
        print(result.model_dump())
        print(element_result.model_dump())
        print(annotation_result.model_dump())
        print(narration_result.model_dump())
        print(handoff_result.model_dump())
        print(intake.model_dump())
        print(replay.model_dump())
        print(desktop.model_dump())


if __name__ == "__main__":
    run()
