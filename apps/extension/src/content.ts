function cssPath(element: Element): string {
  const parts: string[] = [];
  let current: Element | null = element;
  while (current && current.nodeType === Node.ELEMENT_NODE && parts.length < 8) {
    let selector = current.nodeName.toLowerCase();
    if ((current as HTMLElement).id) {
      selector += `#${CSS.escape((current as HTMLElement).id)}`;
      parts.unshift(selector);
      break;
    }
    const testId = (current as HTMLElement).dataset?.testid;
    if (testId) selector += `[data-testid="${CSS.escape(testId)}"]`;
    parts.unshift(selector);
    current = current.parentElement;
  }
  return parts.join(" > ");
}

function elementMetadata(element: Element) {
  const rect = element.getBoundingClientRect();
  const html = element as HTMLElement;
  const testId = html.dataset?.testid;
  return {
    elementRef: `e_${Date.now()}`,
    timestampMs: 0,
    url: location.href,
    role: element.getAttribute("role") || undefined,
    name: element.getAttribute("aria-label") || element.getAttribute("title") || undefined,
    text: html.innerText?.trim().slice(0, 500) || undefined,
    boundingBox: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
    selectors: [
      ...(testId ? [{ type: "testid", value: testId }] : []),
      { type: "css", value: cssPath(element) },
    ],
    domPath: cssPath(element),
  };
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "POINTSPEAK_GET_ELEMENT_AT" && typeof message.x === "number" && typeof message.y === "number") {
    const el = document.elementFromPoint(message.x, message.y);
    sendResponse(el ? elementMetadata(el) : null);
    return true;
  }
  return false;
});
