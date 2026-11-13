import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import { unified } from '@astrojs/markdown-remark';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import mathSearch from './plugins/math-search.mjs';
import rebaseLinks from './plugins/rebase-links.mjs';

const manualBase = (process.env.DIOPTAS_MANUAL_BASE || '/Dioptas/manual').replace(/\/$/, '');
const sourceRef = process.env.DIOPTAS_MANUAL_REF || 'develop';

export default defineConfig({
  site: process.env.DIOPTAS_MANUAL_SITE || 'https://dioptas.github.io',
  base: manualBase,
  trailingSlash: 'always',
  markdown: { processor: unified({ remarkPlugins: [remarkMath], rehypePlugins: [rehypeKatex, mathSearch, [rebaseLinks, { base: manualBase }]] }) },
  integrations: [
    starlight({
      title: 'Dioptas manual',
      description: 'A practical guide to calibrating, masking and integrating X-ray diffraction images in Dioptas.',
      favicon: '/favicon.svg',
      head: [{ tag: 'script', attrs: { src: `${manualBase}/screenshot-zoom.js`, defer: true } }],
      social: [{ icon: 'github', label: 'Source code', href: `https://github.com/Dioptas/Dioptas/tree/${sourceRef}` }],
      editLink: { baseUrl: `https://github.com/Dioptas/Dioptas/edit/${sourceRef}/manual/` },
      customCss: ['katex/dist/katex.min.css', './src/styles/custom.css'],
      sidebar: [
        { slug: 'index', label: 'About this manual' },
        { label: 'Start here', items: ['getting-started/installation', 'getting-started/workspace', 'getting-started/first-pattern'] },
        { label: 'Prepare the detector', items: ['guides/calibration', 'guides/mask'] },
        { label: 'Integration', items: ['integration/image', 'integration/pattern', 'integration/background', 'integration/corrections', 'integration/overlays', 'integration/phases'] },
        { label: 'Series and maps', items: ['guides/batch', 'guides/map'] },
        { label: 'Single crystals', items: ['guides/single-crystal'] },
        { label: 'Projects and customizing', items: ['guides/projects-and-configurations', 'guides/custom-actions'] },
        { label: 'Reference', items: ['reference/settings', 'reference/shortcuts'], collapsed: true },
      ],
    }),
  ],
});
