export interface GraphLinkInput {
  index: number;
  score: number;
}

/**
 * Bridge for future Rust/WASM hotspot migration.
 * Current implementation stays in TypeScript for zero-install fallback.
 */
export function buildMemoryEdges(inputs: GraphLinkInput[]) {
  const edges: Array<{ id: string; source: string; target: string }> = [];
  for (const item of inputs) {
    if (item.index > 0 && item.score > 0.5) {
      edges.push({
        id: `edge-${item.index}`,
        source: `memory-${item.index - 1}`,
        target: `memory-${item.index}`,
      });
    }
  }
  return edges;
}
