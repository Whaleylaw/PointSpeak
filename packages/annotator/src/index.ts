export interface AnnotationDraft {
  id: string;
  kind: "rectangle" | "arrow" | "text" | "pin";
}

export function createAnnotationId(prefix = "a"): string {
  return `${prefix}_${crypto.randomUUID()}`;
}
