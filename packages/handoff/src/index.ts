import type { ElementRef, PageMetadata } from "@pointspeak/schema";

export interface HandoffInput {
  title: string;
  userRequest: string;
  page: PageMetadata;
  elements: ElementRef[];
  bundlePath: string;
}

export function renderMarkdownHandoff(input: HandoffInput): string {
  const elements = input.elements
    .map((el) => `- ${el.elementRef}: ${el.role ?? "element"} ${JSON.stringify(el.name ?? el.text ?? "")}`)
    .join("\n");

  return `# PointSpeak Brief: ${input.title}\n\n## User Request\n${input.userRequest}\n\n## Page\n- URL: ${input.page.url}\n- Title: ${input.page.title ?? ""}\n- Viewport: ${input.page.viewport.width}x${input.page.viewport.height} @ ${input.page.viewport.devicePixelRatio}\n\n## Referenced Elements\n${elements || "_None captured yet._"}\n\n## Artifacts\n- Bundle: ${input.bundlePath}\n`;
}
