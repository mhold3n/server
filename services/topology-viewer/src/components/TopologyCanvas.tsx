import { useCallback, useEffect, useMemo } from 'react';
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Edge,
  type Node,
  type NodeMouseHandler,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import type { TopologyEdge, TopologyNode } from '../topology/types';
import { layoutNodesByGroup, nodePosition } from '../topology/layout';

function FitViewEffect({ viewId }: { viewId: string }) {
  const { fitView } = useReactFlow();
  useEffect(() => {
    const id = requestAnimationFrame(() => {
      void fitView({ padding: 0.2, duration: 250 });
    });
    return () => cancelAnimationFrame(id);
  }, [viewId, fitView]);
  return null;
}

function toRfNodes(
  topoNodes: TopologyNode[],
  positions: Map<string, { x: number; y: number }>,
  selectedId: string | null,
): Node[] {
  return topoNodes.map((n) => ({
    id: n.id,
    position: nodePosition(n, positions),
    data: { label: n.label },
    selected: n.id === selectedId,
  }));
}

function toRfEdges(topoEdges: TopologyEdge[]): Edge[] {
  return topoEdges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    label: e.label,
    animated: e.kind === 'async',
    style:
      e.kind === 'observability'
        ? { strokeDasharray: '6 4' }
        : e.kind === 'data'
          ? { strokeWidth: 2 }
          : undefined,
  }));
}

export interface TopologyCanvasProps {
  viewId: string;
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  selectedId: string | null;
  onSelectId: (id: string | null) => void;
}

export function TopologyCanvas({
  viewId,
  nodes: topoNodes,
  edges: topoEdges,
  selectedId,
  onSelectId,
}: TopologyCanvasProps) {
  const positions = useMemo(() => layoutNodesByGroup(topoNodes), [topoNodes]);
  const initialNodes = useMemo(
    () => toRfNodes(topoNodes, positions, selectedId),
    [topoNodes, positions, selectedId],
  );
  const initialEdges = useMemo(() => toRfEdges(topoEdges), [topoEdges]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    setNodes(toRfNodes(topoNodes, positions, selectedId));
    setEdges(toRfEdges(topoEdges));
  }, [
    viewId,
    topoNodes,
    topoEdges,
    positions,
    selectedId,
    setNodes,
    setEdges,
  ]);

  const onNodeClick = useCallback<NodeMouseHandler>(
    (_, node) => {
      onSelectId(node.id);
    },
    [onSelectId],
  );

  const onPaneClick = useCallback(() => {
    onSelectId(null);
  }, [onSelectId]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onNodeClick={onNodeClick}
      onPaneClick={onPaneClick}
    >
      <Background />
      <Controls />
      <MiniMap pannable zoomable />
      <FitViewEffect viewId={viewId} />
    </ReactFlow>
  );
}
