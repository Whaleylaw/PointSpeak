import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

function App() {
  const [session, setSession] = useState<unknown>(null);

  useEffect(() => {
    chrome.storage.local.get("lastPointSpeakSession").then((value) => {
      setSession(value.lastPointSpeakSession ?? null);
    });
  }, []);

  return (
    <main style={{ fontFamily: "system-ui", padding: 16 }}>
      <h1>PointSpeak</h1>
      <p>Milestone 0 extension shell is installed.</p>
      <pre style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>{JSON.stringify(session, null, 2)}</pre>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
