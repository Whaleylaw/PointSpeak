export type AnnotationKind = "rectangle" | "arrow" | "freehand" | "text" | "pin";

export interface AnnotationDraft {
  annotationId: string;
  type: AnnotationKind;
  targetElementRefs: string[];
  text?: string;
}

export function createAnnotationId(prefix = "a"): string {
  return `${prefix}_${crypto.randomUUID()}`;
}
