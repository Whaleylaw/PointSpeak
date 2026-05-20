const RECEIVER_URL = "http://127.0.0.1:48321";

chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(console.error);
});

chrome.action.onClicked.addListener(async (tab) => {
  if (!tab.id || !tab.windowId) return;

  const screenshot = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });

  const [pageResult] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
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

  const response = await fetch(`${RECEIVER_URL}/sessions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      mode: "snapshot",
      source: "chrome-extension",
      page: pageResult.result,
      screenshotDataUrl: screenshot,
    }),
  });

  if (!response.ok) {
    console.error("PointSpeak receiver rejected session", await response.text());
    return;
  }

  const session = await response.json();
  await chrome.storage.local.set({ lastPointSpeakSession: session });
  console.log("PointSpeak session created", session);
});
