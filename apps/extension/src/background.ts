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

    const session = await response.json();
    await chrome.storage.local.set({ lastPointSpeakSession: session });
    await setBadge("OK", "#16a34a");
    await clearBadgeSoon();
    console.log("PointSpeak session created", session);
  } catch (error) {
    await setBadge("ERR", "#dc2626");
    await clearBadgeSoon();
    console.error("PointSpeak capture failed", error);
    await chrome.storage.local.set({
      lastPointSpeakError: error instanceof Error ? error.message : String(error),
    });
  }
});
