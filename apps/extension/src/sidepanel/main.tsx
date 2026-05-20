import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

type LastSession = {
  sessionId: string;
  bundlePath: string;
  handoff: string;
  manifest: string;
};

type LastElement = {
  sessionId: string;
  elementRef: string;
  elementsPath: string;
  handoff: string;
};

type LastAnnotation = {
  sessionId: string;
  annotationId: string;
  annotationsPath: string;
  handoff: string;
};

type LastHandoff = {
  sessionId: string;
  status: "dry_run" | "submitted" | "failed";
  runId?: string;
  hermesApiUrl: string;
  requestPath: string;
  handoff: string;
  error?: string;
};

type LastNarration = {
  sessionId: string;
  narrationId: string;
  audioPath?: string;
  narrationsPath: string;
  handoff: string;
};

function App() {
  const [session, setSession] = useState<LastSession | null>(null);
  const [element, setElement] = useState<LastElement | null>(null);
  const [annotation, setAnnotation] = useState<LastAnnotation | null>(null);
  const [narration, setNarration] = useState<LastNarration | null>(null);
  const [handoff, setHandoff] = useState<LastHandoff | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    chrome.storage.local
      .get([
        "lastPointSpeakSession",
        "lastPointSpeakElement",
        "lastPointSpeakAnnotation",
        "lastPointSpeakNarration",
        "lastPointSpeakHandoff",
        "lastPointSpeakError",
      ])
      .then((value) => {
        setSession((value.lastPointSpeakSession as LastSession | undefined) ?? null);
        setElement((value.lastPointSpeakElement as LastElement | undefined) ?? null);
        setAnnotation((value.lastPointSpeakAnnotation as LastAnnotation | undefined) ?? null);
        setNarration((value.lastPointSpeakNarration as LastNarration | undefined) ?? null);
        setHandoff((value.lastPointSpeakHandoff as LastHandoff | undefined) ?? null);
        setError((value.lastPointSpeakError as string | undefined) ?? null);
      });
  }, []);

  return (
    <main style={{ fontFamily: "system-ui", padding: 16, lineHeight: 1.4 }}>
      <h1>PointSpeak</h1>
      <p>
        Click the extension button to capture the active tab, click an element, drag an annotation rectangle, and optionally
        record a short narration for the agent.
      </p>
      <p>
        Receiver: <code>http://127.0.0.1:48321</code>
      </p>
      {session ? (
        <section>
          <h2>Last Snapshot</h2>
          <dl>
            <dt>Session</dt>
            <dd>
              <code>{session.sessionId}</code>
            </dd>
            <dt>Bundle</dt>
            <dd>
              <code>{session.bundlePath}</code>
            </dd>
            <dt>Handoff</dt>
            <dd>
              <code>{session.handoff}</code>
            </dd>
          </dl>
        </section>
      ) : (
        <p>No snapshot captured yet.</p>
      )}
      {element ? (
        <section>
          <h2>Last Element</h2>
          <dl>
            <dt>Element Ref</dt>
            <dd>
              <code>{element.elementRef}</code>
            </dd>
            <dt>Elements File</dt>
            <dd>
              <code>{element.elementsPath}</code>
            </dd>
          </dl>
        </section>
      ) : null}
      {annotation ? (
        <section>
          <h2>Last Annotation</h2>
          <dl>
            <dt>Annotation</dt>
            <dd>
              <code>{annotation.annotationId}</code>
            </dd>
            <dt>Annotations File</dt>
            <dd>
              <code>{annotation.annotationsPath}</code>
            </dd>
          </dl>
        </section>
      ) : null}
      {narration ? (
        <section>
          <h2>Last Narration</h2>
          <dl>
            <dt>Narration</dt>
            <dd>
              <code>{narration.narrationId}</code>
            </dd>
            {narration.audioPath ? (
              <>
                <dt>Audio</dt>
                <dd>
                  <code>{narration.audioPath}</code>
                </dd>
              </>
            ) : null}
            <dt>Narrations File</dt>
            <dd>
              <code>{narration.narrationsPath}</code>
            </dd>
          </dl>
        </section>
      ) : null}
      {handoff ? (
        <section>
          <h2>Hermes Handoff</h2>
          <dl>
            <dt>Status</dt>
            <dd>
              <code>{handoff.status}</code>
            </dd>
            <dt>Hermes API</dt>
            <dd>
              <code>{handoff.hermesApiUrl}</code>
            </dd>
            {handoff.runId ? (
              <>
                <dt>Run</dt>
                <dd>
                  <code>{handoff.runId}</code>
                </dd>
              </>
            ) : null}
            <dt>Request</dt>
            <dd>
              <code>{handoff.requestPath}</code>
            </dd>
          </dl>
        </section>
      ) : null}
      {error ? (
        <section style={{ color: "#b91c1c" }}>
          <h2>Last Error</h2>
          <pre style={{ whiteSpace: "pre-wrap" }}>{error}</pre>
        </section>
      ) : null}
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
