type Selector = {
  type: "testid" | "aria" | "css" | "xpath" | "text" | "domPath";
  value: string;
  confidence?: number;
};

type ElementMetadata = {
  elementRef: string;
  timestampMs: number;
  url: string;
  role?: string;
  name?: string;
  text?: string;
  tagName?: string;
  boundingBox?: { x: number; y: number; width: number; height: number };
  selectors: Selector[];
  domPath?: string;
  stateHash?: string;
  metadata: Record<string, unknown>;
};

type AnnotationDraft = {
  annotationId: string;
  type: "rectangle" | "pin";
  timestampMs: number;
  text?: string;
  targetElementRefs: string[];
  color: string;
  shape: {
    x: number;
    y: number;
    width: number;
    height: number;
    pageX: number;
    pageY: number;
    coordinateSpace: "viewport";
  };
  metadata: Record<string, unknown>;
};

const ANNOTATION_COLOR = "#f97316";

let pickOverlay: HTMLDivElement | null = null;
let hoverBox: HTMLDivElement | null = null;
let activeSessionId: string | null = null;
let activeElementRef: string | null = null;
let annotationOverlay: HTMLDivElement | null = null;
let annotationBox: HTMLDivElement | null = null;
let annotationStart: { x: number; y: number } | null = null;
let annotationLatest: { x: number; y: number } | null = null;

function cssPath(element: Element): string {
  const parts: string[] = [];
  let current: Element | null = element;
  while (current && current.nodeType === Node.ELEMENT_NODE && parts.length < 8) {
    let selector = current.nodeName.toLowerCase();
    const html = current as HTMLElement;
    if (html.id) {
      selector += `#${CSS.escape(html.id)}`;
      parts.unshift(selector);
      break;
    }
    const testId = html.dataset?.testid;
    if (testId) selector += `[data-testid="${CSS.escape(testId)}"]`;
    parts.unshift(selector);
    current = current.parentElement;
  }
  return parts.join(" > ");
}

function xpathFor(element: Element): string {
  if ((element as HTMLElement).id) {
    return `//*[@id=${JSON.stringify((element as HTMLElement).id)}]`;
  }
  const segments: string[] = [];
  let current: Element | null = element;
  while (current && current.nodeType === Node.ELEMENT_NODE) {
    const tag = current.nodeName.toLowerCase();
    let index = 1;
    let sibling = current.previousElementSibling;
    while (sibling) {
      if (sibling.nodeName.toLowerCase() === tag) index += 1;
      sibling = sibling.previousElementSibling;
    }
    segments.unshift(`${tag}[${index}]`);
    current = current.parentElement;
  }
  return `/${segments.join("/")}`;
}

function inferRole(element: Element): string | undefined {
  const explicit = element.getAttribute("role");
  if (explicit) return explicit;
  const tag = element.tagName.toLowerCase();
  if (tag === "button") return "button";
  if (tag === "a" && element.hasAttribute("href")) return "link";
  if (tag === "input") return (element as HTMLInputElement).type || "input";
  if (tag === "select") return "select";
  if (tag === "textarea") return "textbox";
  if (/^h[1-6]$/.test(tag)) return "heading";
  return undefined;
}

function accessibleName(element: Element): string | undefined {
  const aria = element.getAttribute("aria-label");
  if (aria) return aria.trim();
  const labelledBy = element.getAttribute("aria-labelledby");
  if (labelledBy) {
    const label = labelledBy
      .split(/\s+/)
      .map((id) => document.getElementById(id)?.innerText.trim())
      .filter(Boolean)
      .join(" ");
    if (label) return label;
  }
  const title = element.getAttribute("title");
  if (title) return title.trim();
  const html = element as HTMLElement;
  const text = html.innerText?.trim();
  return text ? text.slice(0, 160) : undefined;
}

async function sha256Hex(input: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(input));
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function elementMetadata(element: Element): Promise<ElementMetadata> {
  const rect = element.getBoundingClientRect();
  const html = element as HTMLElement;
  const testId = html.dataset?.testid;
  const role = inferRole(element);
  const name = accessibleName(element);
  const text = html.innerText?.trim().replace(/\s+/g, " ").slice(0, 500) || undefined;
  const domPath = cssPath(element);
  const selectors: Selector[] = [];
  if (testId) selectors.push({ type: "testid", value: testId, confidence: 0.95 });
  if (role && name) selectors.push({ type: "aria", value: `${role}[name=${JSON.stringify(name)}]`, confidence: 0.85 });
  selectors.push({ type: "css", value: domPath, confidence: testId ? 0.7 : 0.55 });
  selectors.push({ type: "xpath", value: xpathFor(element), confidence: 0.45 });
  if (text) selectors.push({ type: "text", value: text.slice(0, 120), confidence: 0.35 });

  const stateHash = await sha256Hex(JSON.stringify({ url: location.href, role, name, text, domPath }));

  return {
    elementRef: `e_${Date.now().toString(36)}`,
    timestampMs: 0,
    url: location.href,
    role,
    name,
    text,
    tagName: element.tagName.toLowerCase(),
    boundingBox: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
    selectors,
    domPath,
    stateHash,
    metadata: {
      id: html.id || undefined,
      className: typeof html.className === "string" ? html.className : undefined,
      testId,
    },
  };
}

function ensurePickOverlay(): void {
  if (pickOverlay && hoverBox) return;

  pickOverlay = document.createElement("div");
  pickOverlay.id = "pointspeak-pick-overlay";
  pickOverlay.textContent = "PointSpeak: click an element to attach it to the snapshot · Esc to cancel";
  Object.assign(pickOverlay.style, {
    position: "fixed",
    top: "12px",
    left: "50%",
    transform: "translateX(-50%)",
    zIndex: "2147483647",
    background: "#111827",
    color: "white",
    padding: "8px 12px",
    borderRadius: "999px",
    font: "13px system-ui, sans-serif",
    boxShadow: "0 6px 20px rgba(0,0,0,.25)",
    pointerEvents: "none",
  });

  hoverBox = document.createElement("div");
  hoverBox.id = "pointspeak-hover-box";
  Object.assign(hoverBox.style, {
    position: "fixed",
    zIndex: "2147483646",
    border: "2px solid #2563eb",
    background: "rgba(37, 99, 235, 0.12)",
    pointerEvents: "none",
    display: "none",
    boxSizing: "border-box",
  });

  document.documentElement.append(pickOverlay, hoverBox);
}

function removePickOverlay(): void {
  pickOverlay?.remove();
  hoverBox?.remove();
  pickOverlay = null;
  hoverBox = null;
}

function updateHoverBox(event: MouseEvent): void {
  if (!hoverBox) return;
  const target = document.elementFromPoint(event.clientX, event.clientY);
  if (!target || target === pickOverlay || target === hoverBox) {
    hoverBox.style.display = "none";
    return;
  }
  const rect = target.getBoundingClientRect();
  Object.assign(hoverBox.style, {
    display: "block",
    left: `${rect.left}px`,
    top: `${rect.top}px`,
    width: `${rect.width}px`,
    height: `${rect.height}px`,
  });
}

async function handlePickClick(event: MouseEvent): Promise<void> {
  event.preventDefault();
  event.stopPropagation();
  const target = document.elementFromPoint(event.clientX, event.clientY);
  if (!target || !activeSessionId) return;
  const metadata = await elementMetadata(target);
  const sessionId = activeSessionId;
  removePickMode();
  chrome.runtime.sendMessage({
    type: "POINTSPEAK_ELEMENT_PICKED",
    sessionId,
    element: metadata,
  });
}

function handlePickKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") {
    removePickMode();
    chrome.runtime.sendMessage({ type: "POINTSPEAK_ELEMENT_PICK_CANCELLED", sessionId: activeSessionId });
  }
}

function removePickMode(): void {
  document.removeEventListener("mousemove", updateHoverBox, true);
  document.removeEventListener("click", handlePickClick, true);
  document.removeEventListener("keydown", handlePickKeydown, true);
  activeSessionId = null;
  removePickOverlay();
}

function startPickMode(sessionId: string): void {
  removePickMode();
  removeAnnotationMode();
  activeSessionId = sessionId;
  ensurePickOverlay();
  document.addEventListener("mousemove", updateHoverBox, true);
  document.addEventListener("click", handlePickClick, true);
  document.addEventListener("keydown", handlePickKeydown, true);
}

function ensureAnnotationOverlay(): void {
  if (annotationOverlay && annotationBox) return;

  annotationOverlay = document.createElement("div");
  annotationOverlay.id = "pointspeak-annotation-overlay";
  Object.assign(annotationOverlay.style, {
    position: "fixed",
    inset: "0",
    zIndex: "2147483645",
    cursor: "crosshair",
    background: "rgba(17, 24, 39, 0.04)",
  });

  const pill = document.createElement("div");
  pill.textContent = "PointSpeak: drag a rectangle for the agent, then add a short note · Esc to skip";
  Object.assign(pill.style, {
    position: "fixed",
    top: "12px",
    left: "50%",
    transform: "translateX(-50%)",
    background: "#111827",
    color: "white",
    padding: "8px 12px",
    borderRadius: "999px",
    font: "13px system-ui, sans-serif",
    boxShadow: "0 6px 20px rgba(0,0,0,.25)",
    pointerEvents: "none",
  });

  annotationBox = document.createElement("div");
  annotationBox.id = "pointspeak-annotation-box";
  Object.assign(annotationBox.style, {
    position: "fixed",
    border: `3px solid ${ANNOTATION_COLOR}`,
    background: "rgba(249, 115, 22, 0.14)",
    boxSizing: "border-box",
    display: "none",
    pointerEvents: "none",
  });

  annotationOverlay.append(pill, annotationBox);
  document.documentElement.append(annotationOverlay);
}

function updateAnnotationBox(): void {
  if (!annotationBox || !annotationStart || !annotationLatest) return;
  const left = Math.min(annotationStart.x, annotationLatest.x);
  const top = Math.min(annotationStart.y, annotationLatest.y);
  const width = Math.abs(annotationLatest.x - annotationStart.x);
  const height = Math.abs(annotationLatest.y - annotationStart.y);
  Object.assign(annotationBox.style, {
    display: "block",
    left: `${left}px`,
    top: `${top}px`,
    width: `${Math.max(width, 1)}px`,
    height: `${Math.max(height, 1)}px`,
  });
}

function handleAnnotationMouseDown(event: MouseEvent): void {
  if (!annotationOverlay || event.target !== annotationOverlay) return;
  event.preventDefault();
  event.stopPropagation();
  annotationStart = { x: event.clientX, y: event.clientY };
  annotationLatest = { ...annotationStart };
  updateAnnotationBox();
}

function handleAnnotationMouseMove(event: MouseEvent): void {
  if (!annotationStart) return;
  event.preventDefault();
  event.stopPropagation();
  annotationLatest = { x: event.clientX, y: event.clientY };
  updateAnnotationBox();
}

function buildAnnotation(text?: string): AnnotationDraft | null {
  if (!annotationStart || !annotationLatest || !activeElementRef) return null;
  const left = Math.min(annotationStart.x, annotationLatest.x);
  const top = Math.min(annotationStart.y, annotationLatest.y);
  const width = Math.abs(annotationLatest.x - annotationStart.x);
  const height = Math.abs(annotationLatest.y - annotationStart.y);
  const isPin = width < 8 && height < 8;

  return {
    annotationId: `a_${Date.now().toString(36)}`,
    type: isPin ? "pin" : "rectangle",
    timestampMs: 0,
    text: text?.trim() || undefined,
    targetElementRefs: [activeElementRef],
    color: ANNOTATION_COLOR,
    shape: {
      x: left,
      y: top,
      width: isPin ? 1 : width,
      height: isPin ? 1 : height,
      pageX: left + window.scrollX,
      pageY: top + window.scrollY,
      coordinateSpace: "viewport",
    },
    metadata: {
      url: location.href,
      viewport: { width: window.innerWidth, height: window.innerHeight, devicePixelRatio: window.devicePixelRatio || 1 },
      scroll: { x: window.scrollX, y: window.scrollY },
    },
  };
}

function handleAnnotationMouseUp(event: MouseEvent): void {
  if (!annotationStart || !activeSessionId) return;
  event.preventDefault();
  event.stopPropagation();
  annotationLatest = { x: event.clientX, y: event.clientY };
  updateAnnotationBox();

  const sessionId = activeSessionId;
  const note = window.prompt("PointSpeak note for the agent?", "Look here");
  const annotation = buildAnnotation(note ?? undefined);
  removeAnnotationMode();
  if (!annotation) return;
  chrome.runtime.sendMessage({
    type: "POINTSPEAK_ANNOTATION_CREATED",
    sessionId,
    annotation,
  });
}

function handleAnnotationKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") {
    removeAnnotationMode();
    chrome.runtime.sendMessage({ type: "POINTSPEAK_ANNOTATION_CANCELLED", sessionId: activeSessionId });
  }
}

function removeAnnotationMode(): void {
  document.removeEventListener("mousedown", handleAnnotationMouseDown, true);
  document.removeEventListener("mousemove", handleAnnotationMouseMove, true);
  document.removeEventListener("mouseup", handleAnnotationMouseUp, true);
  document.removeEventListener("keydown", handleAnnotationKeydown, true);
  annotationOverlay?.remove();
  annotationOverlay = null;
  annotationBox = null;
  annotationStart = null;
  annotationLatest = null;
  activeSessionId = null;
  activeElementRef = null;
}

function startAnnotationMode(sessionId: string, elementRef: string): void {
  removePickMode();
  removeAnnotationMode();
  activeSessionId = sessionId;
  activeElementRef = elementRef;
  ensureAnnotationOverlay();
  document.addEventListener("mousedown", handleAnnotationMouseDown, true);
  document.addEventListener("mousemove", handleAnnotationMouseMove, true);
  document.addEventListener("mouseup", handleAnnotationMouseUp, true);
  document.addEventListener("keydown", handleAnnotationKeydown, true);
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "POINTSPEAK_GET_ELEMENT_AT" && typeof message.x === "number" && typeof message.y === "number") {
    const el = document.elementFromPoint(message.x, message.y);
    if (!el) {
      sendResponse(null);
      return true;
    }
    elementMetadata(el).then(sendResponse).catch((error) => sendResponse({ error: String(error) }));
    return true;
  }

  if (message?.type === "POINTSPEAK_START_ELEMENT_PICK" && typeof message.sessionId === "string") {
    startPickMode(message.sessionId);
    sendResponse({ ok: true });
    return true;
  }

  if (
    message?.type === "POINTSPEAK_START_ANNOTATION" &&
    typeof message.sessionId === "string" &&
    typeof message.elementRef === "string"
  ) {
    startAnnotationMode(message.sessionId, message.elementRef);
    sendResponse({ ok: true });
    return true;
  }

  return false;
});
