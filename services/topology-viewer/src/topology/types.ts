export type EdgeKind =
  | 'request'
  | 'control'
  | 'data'
  | 'async'
  | 'observability';

export interface TopologyNodeMeta {
  purpose?: string;
  inputs?: string[];
  outputs?: string[];
  endpoint?: string;
  notes?: string;
  /** Placeholder for future live status wiring */
  status?: string;
}

export interface TopologyNode {
  id: string;
  label: string;
  type: string;
  group?: string;
  meta?: TopologyNodeMeta;
  position?: { x: number; y: number };
}

export interface TopologyEdge {
  id: string;
  source: string;
  target: string;
  kind: EdgeKind;
  label?: string;
}

export interface TopologyView {
  id: string;
  label: string;
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}

export interface TopologyDocument {
  views: TopologyView[];
  moduleIndex?: Record<string, TopologyNode>;
}
