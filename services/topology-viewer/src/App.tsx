import { useCallback, useEffect, useMemo, useState } from 'react';
import { ReactFlowProvider } from '@xyflow/react';
import { TopologyCanvas } from './components/TopologyCanvas';
import { InspectorPanel } from './components/InspectorPanel';
import { ModuleTree } from './components/ModuleTree';
import {
  assertViewGraphClosed,
  parseTopologyDocument,
} from './topology/schema';
import type { TopologyDocument, TopologyNode } from './topology/types';
import './App.css';

async function loadTopology(url: string): Promise<TopologyDocument> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to load topology: ${res.status} ${res.statusText}`);
  }
  const json: unknown = await res.json();
  const doc = parseTopologyDocument(json);
  for (const v of doc.views) {
    assertViewGraphClosed(v);
  }
  return doc;
}

function AppInner() {
  const [doc, setDoc] = useState<TopologyDocument | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [viewIndex, setViewIndex] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const dataUrl = `${import.meta.env.BASE_URL}topology.json`;

  useEffect(() => {
    let cancelled = false;
    void loadTopology(dataUrl)
      .then((d) => {
        if (!cancelled) {
          setDoc(d);
          setLoadError(null);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setLoadError(e instanceof Error ? e.message : String(e));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [dataUrl]);

  const view = doc?.views[viewIndex];
  const nodesById = useMemo(() => {
    const map = new Map<string, TopologyNode>();
    if (!view) return map;
    for (const n of view.nodes) {
      map.set(n.id, n);
    }
    return map;
  }, [view]);

  const selectedNode = selectedId ? (nodesById.get(selectedId) ?? null) : null;

  const onSelectId = useCallback((id: string | null) => {
    setSelectedId(id);
  }, []);

  if (loadError) {
    return (
      <div className="app-error">
        <h1>Topology viewer</h1>
        <p>{loadError}</p>
        <p className="mono">{dataUrl}</p>
      </div>
    );
  }

  if (!doc || !view) {
    return (
      <div className="app-loading">
        <p>Loading topology…</p>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Topology</h1>
        <nav className="layer-tabs" aria-label="Layer views">
          {doc.views.map((v, i) => (
            <button
              key={v.id}
              type="button"
              className={i === viewIndex ? 'tab active' : 'tab'}
              onClick={() => {
                setViewIndex(i);
                setSelectedId(null);
              }}
            >
              {v.label}
            </button>
          ))}
        </nav>
      </header>
      <div className="app-body">
        <ModuleTree
          nodes={view.nodes}
          selectedId={selectedId}
          onSelectId={onSelectId}
        />
        <div className="canvas-wrap">
          <TopologyCanvas
            viewId={view.id}
            nodes={view.nodes}
            edges={view.edges}
            selectedId={selectedId}
            onSelectId={onSelectId}
          />
        </div>
        <InspectorPanel
          node={selectedNode}
          edges={view.edges}
          nodesById={nodesById}
        />
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ReactFlowProvider>
      <AppInner />
    </ReactFlowProvider>
  );
}
