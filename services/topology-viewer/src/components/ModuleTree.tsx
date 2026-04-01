import type { TopologyNode } from '../topology/types';

export interface ModuleTreeProps {
  nodes: TopologyNode[];
  selectedId: string | null;
  onSelectId: (id: string | null) => void;
}

export function ModuleTree({
  nodes,
  selectedId,
  onSelectId,
}: ModuleTreeProps) {
  const byGroup = new Map<string, TopologyNode[]>();
  for (const n of nodes) {
    const g = n.group ?? 'other';
    const list = byGroup.get(g);
    if (list) list.push(n);
    else byGroup.set(g, [n]);
  }
  const groups = [...byGroup.entries()].sort(([a], [b]) =>
    a.localeCompare(b),
  );

  return (
    <nav className="module-tree" aria-label="Modules by group">
      <h2 className="module-tree-title">Modules</h2>
      <ul className="module-tree-groups">
        {groups.map(([group, list]) => (
          <li key={group}>
            <span className="module-tree-group">{group}</span>
            <ul>
              {list.map((n) => (
                <li key={n.id}>
                  <button
                    type="button"
                    className={
                      n.id === selectedId
                        ? 'module-tree-node selected'
                        : 'module-tree-node'
                    }
                    onClick={() =>
                      onSelectId(n.id === selectedId ? null : n.id)
                    }
                  >
                    {n.label}
                  </button>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </nav>
  );
}
