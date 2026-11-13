// Pages are authored against /Dioptas/manual/. Rebase those links when the
// manual is published under a different path (DIOPTAS_MANUAL_BASE).
export default function rebaseLinks({ base = '/Dioptas/manual' } = {}) {
  const target = base.replace(/\/$/, '');
  const rewrite = value =>
    typeof value === 'string' && value.startsWith('/Dioptas/manual/')
      ? `${target}/${value.slice('/Dioptas/manual/'.length)}`
      : value;
  return tree => {
    function visit(node) {
      if (node.type === 'element' && node.properties) {
        for (const key of ['href', 'src']) {
          if (key in node.properties) node.properties[key] = rewrite(node.properties[key]);
        }
      }
      node.children?.forEach(visit);
    }
    visit(tree);
  };
}
