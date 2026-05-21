import "./style.css";

type RecorderParams = {
  sessionId: string;
  elementRef?: string;
  annotationId?: string;
};

function parseParams(): RecorderParams {
  const params = new URLSearchParams(location.search);
  const sessionId = params.get("sessionId") || "";
  const elementRef = params.get("elementRef") || undefined;
  const annotationId = params.get("annotationId") || undefined;
  return { sessionId, elementRef, annotationId };
}

function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

function errorText(error: unknown): string {
  if (error instanceof DOMException) {
    return [error.name, error.message].filter(Boolean).join(": ") || "DOMException";
  }
  if (error instanceof Error) {
    return [error.name, error.message].filter(Boolean).join(": ") || "Error";
  }
  return String(error || "Unknown microphone error");
}

const params = parseParams();
const root = document.getElementById("root");
if (!root) throw new Error("Missing root");

root.innerHTML = `
  <main>
    <h1>PointSpeak narration</h1>
    <p>This extension recorder is used when the page blocks microphone access for content scripts.</p>
    <p>Record as long as you need. PointSpeak only sends after you explicitly click <strong>Stop & Send</strong> or <strong>Send captured audio</strong>.</p>
    <p id="status">Ready.</p>
    <div class="controls">
      <button id="record">Start recording</button>
      <button id="send" hidden>Send captured audio</button>
      <button id="skip">Skip</button>
    </div>
  </main>
`;

const status = document.getElementById("status") as HTMLParagraphElement;
const recordButton = document.getElementById("record") as HTMLButtonElement;
const sendButton = document.getElementById("send") as HTMLButtonElement;
const skipButton = document.getElementById("skip") as HTMLButtonElement;
let recorder: MediaRecorder | null = null;
let stream: MediaStream | null = null;
let chunks: Blob[] = [];
let startedAt = 0;
let capturedBlob: Blob | null = null;
let stopWasRequestedByUser = false;
let sent = false;

function closeSoon(): void {
  window.setTimeout(() => window.close(), 1200);
}

function cleanupStream(): void {
  stream?.getTracks().forEach((track) => track.stop());
  stream = null;
}

async function sendCapturedNarration(): Promise<void> {
  if (!capturedBlob || sent) return;
  sent = true;
  recordButton.disabled = true;
  sendButton.disabled = true;
  skipButton.disabled = true;
  status.textContent = "Saving narration…";
  try {
    const blob = capturedBlob;
    const audioDataUrl = await blobToDataUrl(blob);
    chrome.runtime.sendMessage({
      type: "POINTSPEAK_NARRATION_CAPTURED",
      sessionId: params.sessionId,
      narration: {
        narrationId: `n_${Date.now().toString(36)}`,
        timestampMs: 0,
        durationMs: Math.max(0, Date.now() - startedAt),
        audioDataUrl,
        mimeType: blob.type || "audio/webm",
        targetElementRefs: params.elementRef ? [params.elementRef] : [],
        targetAnnotationRefs: params.annotationId ? [params.annotationId] : [],
        metadata: {
          url: "chrome-extension://recorder",
          source: "chrome-extension-recorder-page",
          explicitStop: stopWasRequestedByUser,
        },
      },
    }, (response) => {
      if (chrome.runtime.lastError || !response?.ok) {
        sent = false;
        recordButton.disabled = false;
        sendButton.disabled = false;
        skipButton.disabled = false;
        status.textContent = `Send failed: ${chrome.runtime.lastError?.message || response?.error || "Unknown error"}`;
        return;
      }
      status.textContent = "Narration sent; finalizing…";
      closeSoon();
    });
  } catch (error) {
    sent = false;
    recordButton.disabled = false;
    sendButton.disabled = false;
    skipButton.disabled = false;
    status.textContent = `Save failed: ${errorText(error)}`;
  }
}

skipButton.addEventListener("click", () => {
  if (recorder?.state === "recording") {
    stopWasRequestedByUser = false;
    recorder.stop();
  }
  cleanupStream();
  chrome.runtime.sendMessage({ type: "POINTSPEAK_NARRATION_SKIPPED", sessionId: params.sessionId });
  status.textContent = "Skipped; finalizing…";
  closeSoon();
});

sendButton.addEventListener("click", () => {
  void sendCapturedNarration();
});

recordButton.addEventListener("click", async () => {
  if (recorder?.state === "recording") {
    stopWasRequestedByUser = true;
    recordButton.disabled = true;
    status.textContent = "Stopping and preparing to send…";
    recorder.stop();
    return;
  }

  capturedBlob = null;
  chunks = [];
  sent = false;
  sendButton.hidden = true;

  try {
    recordButton.disabled = true;
    status.textContent = "Requesting microphone…";
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recorder = new MediaRecorder(stream, MediaRecorder.isTypeSupported("audio/webm") ? { mimeType: "audio/webm" } : undefined);
    startedAt = Date.now();
    stopWasRequestedByUser = false;

    recorder.addEventListener("dataavailable", (event) => {
      if (event.data.size > 0) chunks.push(event.data);
    });

    recorder.addEventListener("stop", () => {
      cleanupStream();
      capturedBlob = new Blob(chunks, { type: recorder?.mimeType || "audio/webm" });
      const seconds = Math.round((Date.now() - startedAt) / 1000);
      recordButton.disabled = false;
      recordButton.textContent = "Record again";
      sendButton.hidden = false;
      if (stopWasRequestedByUser) {
        status.textContent = `Recorded ${seconds}s. Sending package…`;
        void sendCapturedNarration();
      } else {
        status.textContent = `Recording stopped unexpectedly after ${seconds}s. Nothing has been sent yet — click Send captured audio or Record again.`;
      }
    });

    recorder.addEventListener("error", (event) => {
      status.textContent = `Recorder error: ${errorText(event.error)}`;
    });

    recorder.start(1000);
    recordButton.disabled = false;
    recordButton.textContent = "Stop & Send";
    status.textContent = "Recording… click Stop & Send when finished.";
  } catch (error) {
    cleanupStream();
    status.textContent = `Microphone unavailable: ${errorText(error)}`;
    recordButton.disabled = false;
  }
});

window.addEventListener("beforeunload", (event) => {
  if (recorder?.state === "recording" || (capturedBlob && !sent)) {
    event.preventDefault();
    event.returnValue = "PointSpeak has an unsent narration.";
  }
});
