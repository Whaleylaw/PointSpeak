import { z } from "zod";

export const PointSpeakModeSchema = z.enum(["snapshot", "walkthrough", "live"]);

export const BoundingBoxSchema = z.object({
  x: z.number(),
  y: z.number(),
  width: z.number(),
  height: z.number(),
});

export const SelectorSchema = z.object({
  type: z.enum(["testid", "aria", "css", "xpath", "text", "domPath"]),
  value: z.string(),
  confidence: z.number().min(0).max(1).optional(),
});

export const PageMetadataSchema = z.object({
  url: z.string(),
  title: z.string().optional(),
  viewport: z.object({
    width: z.number().int().positive(),
    height: z.number().int().positive(),
    devicePixelRatio: z.number().positive(),
  }),
  scroll: z.object({
    x: z.number(),
    y: z.number(),
  }),
  capturedAt: z.string(),
});

export const ElementRefSchema = z.object({
  elementRef: z.string(),
  timestampMs: z.number().nonnegative(),
  url: z.string(),
  role: z.string().optional(),
  name: z.string().optional(),
  text: z.string().optional(),
  boundingBox: BoundingBoxSchema.optional(),
  selectors: z.array(SelectorSchema).default([]),
  domPath: z.string().optional(),
  stateHash: z.string().optional(),
});

export const AnnotationSchema = z.object({
  annotationId: z.string(),
  type: z.enum(["rectangle", "arrow", "freehand", "text", "pin"]),
  timestampMs: z.number().nonnegative(),
  text: z.string().optional(),
  targetElementRefs: z.array(z.string()).default([]),
  shape: z.record(z.unknown()).optional(),
});

export const TimelineEventSchema = z.object({
  eventId: z.string(),
  timestampMs: z.number().nonnegative(),
  type: z.string(),
  visualHash: z.string().optional(),
  stateHash: z.string().optional(),
  media: z.string().optional(),
  data: z.record(z.unknown()).optional(),
});

export const ManifestSchema = z.object({
  schemaVersion: z.string(),
  sessionId: z.string(),
  createdAt: z.string(),
  mode: PointSpeakModeSchema,
  source: z.string(),
  page: z.string().default("page.json"),
  timeline: z.string().default("timeline.ndjson"),
  annotations: z.string().default("annotations.ndjson"),
  elements: z.string().default("elements.ndjson"),
  media: z.array(z.string()).default([]),
  handoff: z.string().default("handoff/latest.md"),
});

export type PointSpeakMode = z.infer<typeof PointSpeakModeSchema>;
export type BoundingBox = z.infer<typeof BoundingBoxSchema>;
export type Selector = z.infer<typeof SelectorSchema>;
export type PageMetadata = z.infer<typeof PageMetadataSchema>;
export type ElementRef = z.infer<typeof ElementRefSchema>;
export type Annotation = z.infer<typeof AnnotationSchema>;
export type TimelineEvent = z.infer<typeof TimelineEventSchema>;
export type Manifest = z.infer<typeof ManifestSchema>;
