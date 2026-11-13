// KaTeX emits MathML (including its TeX annotation) and a visual HTML copy.
// Keep both for rendering/accessibility, but index the visual text only once.
export default function mathSearch() {
  return tree => {
    function walk(node) {
      if (node.type === 'element' && node.properties?.className?.includes('katex-mathml')) {
        node.properties['data-pagefind-ignore'] = 'all';
        return;
      }
      node.children?.forEach(walk);
    }
    walk(tree);
  };
}
