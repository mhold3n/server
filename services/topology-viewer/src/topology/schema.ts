import { z } from 'zod';

const edgeKindSchema = z.enum([
  'request',
  'control',
  'data',
  'async',
  'observability',
]);

const topologyNodeMetaSchema = z
  .object({
    purpose: z.string().optional(),
    inputs: z.array(z.string()).optional(),
    outputs: z.array(z.string()).optional(),
    endpoint: z.string().optional(),
    notes: z.string().optional(),
    status: z.string().optional(),
  })
  .strict();

export const topologyNodeSchema = z
  .object({
    id: z.string().min(1),
    label: z.string().min(1),
    type: z.string().min(1),
    group: z.string().optional(),
    meta: topologyNodeMetaSchema.optional(),
    position: z
      .object({ x: z.number(), y: z.number() })
      .strict()
      .optional(),
  })
  .strict();

export const topologyEdgeSchema = z
  .object({
    id: z.string().min(1),
    source: z.string().min(1),
    target: z.string().min(1),
    kind: edgeKindSchema,
    label: z.string().optional(),
  })
  .strict();

export const topologyViewSchema = z
  .object({
    id: z.string().min(1),
    label: z.string().min(1),
    nodes: z.array(topologyNodeSchema),
    edges: z.array(topologyEdgeSchema),
  })
  .strict();

export const topologyDocumentSchema = z
  .object({
    views: z.array(topologyViewSchema).min(1),
    moduleIndex: z.record(z.string(), topologyNodeSchema).optional(),
  })
  .strict();

export type TopologyDocumentParsed = z.infer<typeof topologyDocumentSchema>;

export function parseTopologyDocument(raw: unknown): TopologyDocumentParsed {
  return topologyDocumentSchema.parse(raw);
}

/** Validate edge endpoints exist on each view (throws if invalid). */
export function assertViewGraphClosed(view: z.infer<typeof topologyViewSchema>): void {
  const ids = new Set(view.nodes.map((n) => n.id));
  for (const e of view.edges) {
    if (!ids.has(e.source)) {
      throw new Error(
        `View "${view.id}": edge ${e.id} references missing source "${e.source}"`,
      );
    }
    if (!ids.has(e.target)) {
      throw new Error(
        `View "${view.id}": edge ${e.id} references missing target "${e.target}"`,
      );
    }
  }
}
