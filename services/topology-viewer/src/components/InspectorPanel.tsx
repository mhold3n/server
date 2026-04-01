import type { TopologyEdge, TopologyNode } from '../topology/types';

export interface InspectorPanelProps {
  node: TopologyNode | null;
  edges: TopologyEdge[];
  nodesById: Map<string, TopologyNode>;
}

function neighborLabels(
  id: string,
  edges: TopologyEdge[],
  nodesById: Map<string, TopologyNode>,
  direction: 'upstream' | 'downstream',
): string[] {
  const names = new Set<string>();
  for (const e of edges) {
    if (direction === 'upstream' && e.target === id) {
      const n = nodesById.get(e.source);
      if (n) names.add(n.label);
    }
    if (direction === 'downstream' && e.source === id) {
      const n = nodesById.get(e.target);
      if (n) names.add(n.label);
    }
  }
  return [...names].sort();
}

export function InspectorPanel({ node, edges, nodesById }: InspectorPanelProps) {
  if (!node) {
    return (
      <aside className="inspector">
        <h2>Module</h2>
        <p className="inspector-hint">Select a node on the graph or in the tree.</p>
      </aside>
    );
  }

  const m = node.meta;
  const upstream = neighborLabels(node.id, edges, nodesById, 'upstream');
  const downstream = neighborLabels(node.id, edges, nodesById, 'downstream');

  return (
    <aside className="inspector">
      <h2>{node.label}</h2>
      <p className="inspector-id mono">{node.id}</p>
      <dl className="inspector-dl">
        <dt>Type</dt>
        <dd>{node.type}</dd>
        {node.group ? (
          <>
            <dt>Group</dt>
            <dd>{node.group}</dd>
          </>
        ) : null}
        {m?.purpose ? (
          <>
            <dt>Purpose</dt>
            <dd>{m.purpose}</dd>
          </>
        ) : null}
        {m?.endpoint ? (
          <>
            <dt>Endpoint</dt>
            <dd className="mono">{m.endpoint}</dd>
          </>
        ) : null}
        {m?.inputs?.length ? (
          <>
            <dt>Inputs</dt>
            <dd>
              <ul>
                {m.inputs.map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ul>
            </dd>
          </>
        ) : null}
        {m?.outputs?.length ? (
          <>
            <dt>Outputs</dt>
            <dd>
              <ul>
                {m.outputs.map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ul>
            </dd>
          </>
        ) : null}
        {m?.notes ? (
          <>
            <dt>Notes</dt>
            <dd>{m.notes}</dd>
          </>
        ) : null}
        {m?.status ? (
          <>
            <dt>Status</dt>
            <dd>{m.status}</dd>
          </>
        ) : null}
        <dt>Upstream</dt>
        <dd>
          {upstream.length ? (
            <ul>
              {upstream.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          ) : (
            <span className="muted">none in this view</span>
          )}
        </dd>
        <dt>Downstream</dt>
        <dd>
          {downstream.length ? (
            <ul>
              {downstream.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          ) : (
            <span className="muted">none in this view</span>
          )}
        </dd>
      </dl>
    </aside>
  );
}
