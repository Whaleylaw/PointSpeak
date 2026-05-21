const RECEIVER_URL = "http://127.0.0.1:48321";

type PageMetadata = {
  url: string;
  title?: string;
  viewport: {
    width: number;
    height: number;
    devicePixelRatio: number;
  };
  scroll: {
    x: number;
    y: number;
  };
  capturedAt: string;
};

type CaptureSession = {
  sessionId: string;
  bundlePath: string;
  handoff: string;
  manifest: string;
};

type AddElementResponse = {
  sessionId: string;
  elementRef: string;
  elementsPath: string;
  handoff: string;
};

type AddAnnotationResponse = {
  sessionId: string;
  annotationId: string;
  annotationsPath: string;
  handoff: string;
};

type SubmitHandoffResponse = {
  sessionId: string;
  status: "dry_run" | "submitted" | "failed";
  runId?: string;
  hermesApiUrl: string;
  requestPath: string;
  handoff: string;
  error?: string;
};

type AddNarrationResponse = {
  sessionId: string;
  narrationId: string;
  audioPath?: string;
  narrationsPath: string;
  handoff: string;
};

type IntakeResponse = {
  sessionId: string;
  intakePath: string;
  actionDraftPath: string;
  replayPath: string;
  summary: string;
  suggestedActions: string[];
  redactionsApplied: string[];
};

type DesktopExportResponse = {
  sessionId: string;
  exportPath: string;
  desktopInbox: string;
};

async function setBadge(text: string, color: string): Promise<void> {
  await chrome.action.setBadgeText({ text });
  await chrome.action.setBadgeBackgroundColor({ color });
}

async function clearBadgeSoon(): Promise<void> {
  setTimeout(() => {
    chrome.action.setBadgeText({ text: "" }).catch(console.error);
  }, 3000);
}

async function readPageMetadata(tabId: number): Promise<PageMetadata> {
  const [pageResult] = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => ({
      url: location.href,
      title: document.title,
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight,
        devicePixelRatio: window.devicePixelRatio || 1,
      },
      scroll: { x: window.scrollX, y: window.scrollY },
      capturedAt: new Date().toISOString(),
    }),
  });

  if (!pageResult.result) {
    throw new Error("Unable to read page metadata from active tab");
  }
  return pageResult.result as PageMetadata;
}

async function ensureContentScript(tabId: number): Promise<void> {
  try {
    await chrome.tabs.sendMessage(tabId, { type: "POINTSPEAK_PING" });
  } catch {
    await chrome.scripting.executeScript({ target: { tabId }, files: ["content.js"] });
  }
}

async function startElementPick(tabId: number, sessionId: string): Promise<void> {
  await ensureContentScript(tabId);
  await chrome.tabs.sendMessage(tabId, { type: "POINTSPEAK_START_ELEMENT_PICK", sessionId });
}

async function startAnnotation(tabId: number, sessionId: string, elementRef: string): Promise<void> {
  await ensureContentScript(tabId);
  await chrome.tabs.sendMessage(tabId, { type: "POINTSPEAK_START_ANNOTATION", sessionId, elementRef });
}

async function startNarration(tabId: number, sessionId: string, elementRef?: string, annotationId?: string): Promise<void> {
  await ensureContentScript(tabId);
  await chrome.tabs.sendMessage(tabId, { type: "POINTSPEAK_START_NARRATION", sessionId, elementRef, annotationId });
}

async function askForAnotherPoint(tabId: number, sessionId: string): Promise<boolean> {
  const [result] = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => window.confirm("Add another PointSpeak capture point to this same session?"),
  });
  if (result.result) {
    await setBadge("PICK", "#7c3aed");
    await startElementPick(tabId, sessionId);
    return true;
  }
  return false;
}

async function postPickedElement(sessionId: string, element: unknown): Promise<AddElementResponse> {
  const response = await fetch(`${RECEIVER_URL}/sessions/${sessionId}/elements`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ element }),
  });

  if (!response.ok) {
    throw new Error(`PointSpeak receiver rejected element: ${await response.text()}`);
  }
  return response.json() as Promise<AddElementResponse>;
}

async function postAnnotation(sessionId: string, annotation: unknown): Promise<AddAnnotationResponse> {
  const response = await fetch(`${RECEIVER_URL}/sessions/${sessionId}/annotations`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ annotation }),
  });

  if (!response.ok) {
    throw new Error(`PointSpeak receiver rejected annotation: ${await response.text()}`);
  }
  return response.json() as Promise<AddAnnotationResponse>;
}

async function postNarration(sessionId: string, narration: unknown): Promise<AddNarrationResponse> {
  const response = await fetch(`${RECEIVER_URL}/sessions/${sessionId}/narrations`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ narration }),
  });

  if (!response.ok) {
    throw new Error(`PointSpeak receiver rejected narration: ${await response.text()}`);
  }
  return response.json() as Promise<AddNarrationResponse>;
}

async function submitHandoff(sessionId: string): Promise<SubmitHandoffResponse> {
  const response = await fetch(`${RECEIVER_URL}/sessions/${sessionId}/handoff`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({}),
  });

  if (!response.ok) {
    throw new Error(`PointSpeak receiver rejected handoff: ${await response.text()}`);
  }
  return response.json() as Promise<SubmitHandoffResponse>;
}

async function createIntake(sessionId: string): Promise<IntakeResponse> {
  const response = await fetch(`${RECEIVER_URL}/sessions/${sessionId}/intake`, { method: "POST" });
  if (!response.ok) throw new Error(`PointSpeak receiver rejected intake: ${await response.text()}`);
  return response.json() as Promise<IntakeResponse>;
}

async function exportDesktop(sessionId: string): Promise<DesktopExportResponse> {
  const response = await fetch(`${RECEIVER_URL}/sessions/${sessionId}/desktop-export`, { method: "POST" });
  if (!response.ok) throw new Error(`PointSpeak receiver rejected desktop export: ${await response.text()}`);
  return response.json() as Promise<DesktopExportResponse>;
}

async function finalizeSession(sessionId: string): Promise<{ intake: IntakeResponse; desktop: DesktopExportResponse; handoff: SubmitHandoffResponse }> {
  const intake = await createIntake(sessionId);
  const desktop = await exportDesktop(sessionId);
  const handoff = await submitHandoff(sessionId);
  await chrome.storage.local.set({
    lastPointSpeakIntake: intake,
    lastPointSpeakDesktopExport: desktop,
    lastPointSpeakHandoff: handoff,
    lastPointSpeakError: handoff.error ?? null,
  });
  return { intake, desktop, handoff };
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.action.setTitle({ title: "Capture PointSpeak snapshot" }).catch(console.error);
});

chrome.action.onClicked.addListener(async (tab) => {
  if (!tab.id || !tab.windowId) return;

  try {
    await setBadge("…", "#2563eb");

    const [screenshot, page] = await Promise.all([
      chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" }),
      readPageMetadata(tab.id),
    ]);

    const response = await fetch(`${RECEIVER_URL}/sessions`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        mode: "snapshot",
        source: "chrome-extension",
        page,
        screenshotDataUrl: screenshot,
      }),
    });

    if (!response.ok) {
      throw new Error(`PointSpeak receiver rejected session: ${await response.text()}`);
    }

    const session = (await response.json()) as CaptureSession;
    await chrome.storage.local.set({ lastPointSpeakSession: session, lastPointSpeakError: null });
    await setBadge("PICK", "#7c3aed");
    await startElementPick(tab.id, session.sessionId);
    console.log("PointSpeak session created; element pick started", session);
  } catch (error) {
    await setBadge("ERR", "#dc2626");
    await clearBadgeSoon();
    console.error("PointSpeak capture failed", error);
    await chrome.storage.local.set({
      lastPointSpeakError: error instanceof Error ? error.message : String(error),
    });
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "POINTSPEAK_ELEMENT_PICKED" && typeof message.sessionId === "string") {
    postPickedElement(message.sessionId, message.element)
      .then(async (result) => {
        await chrome.storage.local.set({ lastPointSpeakElement: result, lastPointSpeakError: null });
        if (sender.tab?.id) {
          await setBadge("DRAW", "#f97316");
          await startAnnotation(sender.tab.id, message.sessionId, result.elementRef);
        } else {
          await setBadge("OK", "#16a34a");
          await clearBadgeSoon();
        }
        sendResponse({ ok: true, result });
      })
      .catch(async (error) => {
        await setBadge("ERR", "#dc2626");
        await clearBadgeSoon();
        await chrome.storage.local.set({ lastPointSpeakError: error instanceof Error ? error.message : String(error) });
        sendResponse({ ok: false, error: error instanceof Error ? error.message : String(error) });
      });
    return true;
  }

  if (message?.type === "POINTSPEAK_ANNOTATION_CREATED" && typeof message.sessionId === "string") {
    postAnnotation(message.sessionId, message.annotation)
      .then(async (result) => {
        await chrome.storage.local.set({ lastPointSpeakAnnotation: result, lastPointSpeakError: null });
        if (sender.tab?.id) {
          await setBadge("REC", "#ef4444");
          const elementRef = Array.isArray(message.annotation?.targetElementRefs) ? message.annotation.targetElementRefs[0] : undefined;
          await startNarration(sender.tab.id, message.sessionId, elementRef, result.annotationId);
          sendResponse({ ok: true, result });
          return;
        }
        await setBadge("SEND", "#2563eb");
        const finalized = await finalizeSession(message.sessionId);
        await setBadge(finalized.handoff.status === "submitted" ? "SENT" : "SAVE", finalized.handoff.status === "submitted" ? "#16a34a" : "#f97316");
        await clearBadgeSoon();
        sendResponse({ ok: true, result, ...finalized });
      })
      .catch(async (error) => {
        await setBadge("ERR", "#dc2626");
        await clearBadgeSoon();
        await chrome.storage.local.set({ lastPointSpeakError: error instanceof Error ? error.message : String(error) });
        sendResponse({ ok: false, error: error instanceof Error ? error.message : String(error) });
      });
    return true;
  }


  if (message?.type === "POINTSPEAK_NARRATION_CAPTURED" && typeof message.sessionId === "string") {
    postNarration(message.sessionId, message.narration)
      .then(async (result) => {
        await chrome.storage.local.set({ lastPointSpeakNarration: result, lastPointSpeakError: null });
        await setBadge("SEND", "#2563eb");
        const finalized = await finalizeSession(message.sessionId);
        await setBadge(finalized.handoff.status === "submitted" ? "SENT" : "SAVE", finalized.handoff.status === "submitted" ? "#16a34a" : "#f97316");
        await clearBadgeSoon();
        sendResponse({ ok: true, result, ...finalized });
      })
      .catch(async (error) => {
        await setBadge("ERR", "#dc2626");
        await clearBadgeSoon();
        await chrome.storage.local.set({ lastPointSpeakError: error instanceof Error ? error.message : String(error) });
        sendResponse({ ok: false, error: error instanceof Error ? error.message : String(error) });
      });
    return true;
  }

  if (message?.type === "POINTSPEAK_NARRATION_SKIPPED" && typeof message.sessionId === "string") {
    submitHandoff(message.sessionId)
      .then(async () => {
        if (sender.tab?.id && await askForAnotherPoint(sender.tab.id, message.sessionId)) {
          sendResponse({ ok: true, continued: true });
          return;
        }
        await setBadge("SEND", "#2563eb");
        const finalized = await finalizeSession(message.sessionId);
        await setBadge(finalized.handoff.status === "submitted" ? "SENT" : "SAVE", finalized.handoff.status === "submitted" ? "#16a34a" : "#f97316");
        await clearBadgeSoon();
        sendResponse({ ok: true, ...finalized });
      })
      .catch(async (error) => {
        await setBadge("ERR", "#dc2626");
        await clearBadgeSoon();
        await chrome.storage.local.set({ lastPointSpeakError: error instanceof Error ? error.message : String(error) });
        sendResponse({ ok: false, error: error instanceof Error ? error.message : String(error) });
      });
    return true;
  }

  if (message?.type === "POINTSPEAK_ELEMENT_PICK_CANCELLED") {
    setBadge("CXL", "#6b7280").then(clearBadgeSoon).catch(console.error);
    return false;
  }

  if (message?.type === "POINTSPEAK_ANNOTATION_CANCELLED") {
    setBadge("SKIP", "#6b7280").then(clearBadgeSoon).catch(console.error);
    return false;
  }

  return false;
});
