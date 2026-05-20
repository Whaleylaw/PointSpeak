import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

type LastSession = {
  sessionId: string;
  bundlePath: string;
  handoff: string;
  manifest: string;
};

function App() {
  const [session, setSession] = useState<LastSession | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    chrome.storage.local.get(["lastPointSpeakSession", "lastPointSpeakError"]).then((value) => {
      setSession((value.lastPointSpeakSession as LastSession | undefined) ?? null);
      setError((value.lastPointSpeakError as string | undefined) ?? null);
    });
  }, []);

  return (
    <main style={{ fontFamily: "system-ui", padding: 16, lineHeight: 1.4 }}>
      <h1>PointSpeak</h1>
      <p>Click the extension button to capture the active tab into the local receiver.</p>
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
