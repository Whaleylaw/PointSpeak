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
  tagName: z.string().optional(),
  boundingBox: BoundingBoxSchema.optional(),
  selectors: z.array(SelectorSchema).default([]),
  domPath: z.string().optional(),
  stateHash: z.string().optional(),
  metadata: z.record(z.unknown()).default({}),
});

export const AnnotationSchema = z.object({
  annotationId: z.string(),
  type: z.enum(["rectangle", "arrow", "freehand", "text", "pin"]),
  timestampMs: z.number().nonnegative(),
  text: z.string().optional(),
  targetElementRefs: z.array(z.string()).default([]),
  color: z.string().optional(),
  shape: z
    .object({
      x: z.number(),
      y: z.number(),
      width: z.number(),
      height: z.number(),
      pageX: z.number().optional(),
      pageY: z.number().optional(),
      coordinateSpace: z.enum(["viewport", "page", "screenshot"]).default("viewport"),
    })
    .optional(),
  metadata: z.record(z.unknown()).default({}),
});

export const NarrationSchema = z.object({
  narrationId: z.string(),
  timestampMs: z.number().nonnegative(),
  durationMs: z.number().nonnegative().optional(),
  transcript: z.string().optional(),
  audio: z.string().optional(),
  mimeType: z.string().default("audio/webm"),
  targetElementRefs: z.array(z.string()).default([]),
  targetAnnotationRefs: z.array(z.string()).default([]),
  metadata: z.record(z.unknown()).default({}),
});

export const RedactionRegionSchema = z.object({
  redactionId: z.string(),
  reason: z.string().default("user-selected"),
  shape: AnnotationSchema.shape.shape.unwrap(),
  replacement: z.string().default("masked"),
});

export const PrivacyControlsSchema = z.object({
  redactTextPatterns: z.boolean().default(true),
  redactEmails: z.boolean().default(true),
  redactPhones: z.boolean().default(true),
  redactCreditCards: z.boolean().default(true),
  redactSecrets: z.boolean().default(true),
  screenshotRegions: z.array(RedactionRegionSchema).default([]),
  notes: z.array(z.string()).default([]),
});

export const CapturePointSchema = z.object({
  pointId: z.string(),
  elements: z.array(ElementRefSchema).default([]),
  annotation: AnnotationSchema.nullable().optional(),
  narrations: z.array(NarrationSchema).default([]),
});

export const AgentIntakeSchema = z.object({
  schemaVersion: z.string(),
  sessionId: z.string(),
  bundlePath: z.string(),
  page: PageMetadataSchema,
  capturePoints: z.array(CapturePointSchema).default([]),
  observedIntent: z.string(),
  summary: z.string(),
  suggestedActions: z.array(z.string()).default([]),
  artifacts: z.record(z.string()).default({}),
  redactionsApplied: z.array(z.string()).default([]),
});

export const BridgeLeaseSchema = z.object({
  agent: z.string(),
  activatedAt: z.string(),
  expiresAt: z.string(),
  ttlMinutes: z.number().int().positive(),
  hermesApiUrl: z.string().optional().nullable(),
  apiKeyEnv: z.string().optional().nullable(),
  model: z.string().optional().nullable(),
  notifyTarget: z.string().optional().nullable(),
  wakeChat: z.boolean().default(true),
  includeBacklogMinutes: z.number().int().nonnegative().default(0),
});

export const BridgeEventSchema = z.object({
  eventId: z.string(),
  createdAt: z.string(),
  sessionId: z.string(),
  bundlePath: z.string(),
  target: z.string(),
  status: z.enum(["queued", "delivered", "failed", "claimed"]),
  claimedBy: z.string().optional().nullable(),
  claimedAt: z.string().optional().nullable(),
  artifacts: z.record(z.string()).default({}),
  delivery: z.record(z.unknown()).optional().nullable(),
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
  narrations: z.string().default("narrations.ndjson"),
  media: z.array(z.string()).default([]),
  handoff: z.string().default("handoff/latest.md"),
  intake: z.string().default("handoff/intake.json"),
  actionDraft: z.string().default("handoff/action-draft.md"),
  replay: z.string().default("replay/index.html"),
  desktopExport: z.string().default("desktop/latest.json"),
});

export type PointSpeakMode = z.infer<typeof PointSpeakModeSchema>;
export type BoundingBox = z.infer<typeof BoundingBoxSchema>;
export type Selector = z.infer<typeof SelectorSchema>;
export type PageMetadata = z.infer<typeof PageMetadataSchema>;
export type ElementRef = z.infer<typeof ElementRefSchema>;
export type Annotation = z.infer<typeof AnnotationSchema>;
export type Narration = z.infer<typeof NarrationSchema>;
export type RedactionRegion = z.infer<typeof RedactionRegionSchema>;
export type PrivacyControls = z.infer<typeof PrivacyControlsSchema>;
export type CapturePoint = z.infer<typeof CapturePointSchema>;
export type AgentIntake = z.infer<typeof AgentIntakeSchema>;
export type BridgeLease = z.infer<typeof BridgeLeaseSchema>;
export type BridgeEvent = z.infer<typeof BridgeEventSchema>;
export type TimelineEvent = z.infer<typeof TimelineEventSchema>;
export type Manifest = z.infer<typeof ManifestSchema>;
