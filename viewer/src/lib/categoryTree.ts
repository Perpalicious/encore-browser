import type { Lot } from './types';

// A node in the HiBid category hierarchy. `children` is keyed by the child
// category name. Leaf nodes simply have an empty `children` map.
export interface CatNode {
  children: Record<string, CatNode>;
  count: number; // number of lots at or below this node
}

/**
 * Build a category tree from the lots' `category_path` arrays (root → leaf).
 * Runs once on data load. O(total path elements).
 */
export function buildCategoryTree(lots: Lot[]): CatNode {
  const root: CatNode = { children: {}, count: 0 };
  for (const lot of lots) {
    let node = root;
    node.count++;
    for (const name of lot.category_path) {
      if (!node.children[name]) {
        node.children[name] = { children: {}, count: 0 };
      }
      node = node.children[name];
      node.count++;
    }
  }
  return root;
}

/** Walk the tree by `path`; returns null if the path doesn't exist. */
export function nodeAtPath(root: CatNode, path: string[]): CatNode | null {
  let node: CatNode = root;
  for (const name of path) {
    const next = node.children[name];
    if (!next) return null;
    node = next;
  }
  return node;
}

/** Sorted child category names of the node at `path` (empty if none / missing). */
export function childrenAtPath(root: CatNode, path: string[]): string[] {
  const node = nodeAtPath(root, path);
  if (!node) return [];
  return Object.keys(node.children).sort((a, b) => a.localeCompare(b));
}

/** True if `prefix` is a leading slice of `path`. */
export function pathHasPrefix(path: string[], prefix: string[]): boolean {
  if (prefix.length > path.length) return false;
  for (let i = 0; i < prefix.length; i++) {
    if (path[i] !== prefix[i]) return false;
  }
  return true;
}
