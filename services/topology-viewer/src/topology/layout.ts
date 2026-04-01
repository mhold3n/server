import type { TopologyNode } from './types';

const GROUP_ORDER = [
  'entry',
  'frontend',
  'reasoning',
  'ai-services',
  'data',
  'observability',
  'mcp',
  'worker',
  'other',
];

const COL_GAP = 210;
const ROW_GAP = 130;

/** Assign grid positions by group when JSON omits explicit positions. */
export function layoutNodesByGroup(nodes: TopologyNode[]): Map<string, { x: number; y: number }> {
  const byGroup = new Map<string, TopologyNode[]>();
  for (const n of nodes) {
    const g = n.group ?? 'other';
    const list = byGroup.get(g);
    if (list) list.push(n);
    else byGroup.set(g, [n]);
  }
  const pos = new Map<string, { x: number; y: number }>();
  let row = 0;

  const emitGroup = (nodesInGroup: TopologyNode[]) => {
    let col = 0;
    for (const n of nodesInGroup) {
      if (n.position) {
        pos.set(n.id, n.position);
      } else {
        pos.set(n.id, { x: col * COL_GAP, y: row * ROW_GAP });
        col += 1;
      }
    }
    row += 1;
  };

  for (const g of GROUP_ORDER) {
    const list = byGroup.get(g);
    if (list?.length) emitGroup(list);
    byGroup.delete(g);
  }
  for (const list of byGroup.values()) {
    if (list.length) emitGroup(list);
  }
  return pos;
}

export function nodePosition(
  n: TopologyNode,
  positions: Map<string, { x: number; y: number }>,
): { x: number; y: number } {
  return n.position ?? positions.get(n.id) ?? { x: 0, y: 0 };
}
