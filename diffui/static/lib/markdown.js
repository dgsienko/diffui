import { marked } from 'marked';

marked.setOptions({ breaks: true, gfm: true });

const KROKI_BASE = [
  'mermaid', 'plantuml', 'graphviz', 'dot', 'd2', 'excalidraw',
  'ditaa', 'nomnoml', 'svgbob', 'vega', 'vegalite', 'wavedrom',
  'bytefield', 'pikchr', 'structurizr', 'erd', 'blockdiag',
  'seqdiag', 'actdiag', 'nwdiag', 'packetdiag', 'rackdiag',
];
const KROKI_LANGS = new Set([...KROKI_BASE, ...KROKI_BASE.map(l => `kroki-${l}`)]);

let _diagramId = 0;
const _pendingDiagrams = new Map();

const renderer = {
  code({ text, lang }) {
    const key = lang?.toLowerCase();
    if (key && KROKI_LANGS.has(key)) {
      const id = `kroki-${++_diagramId}`;
      _pendingDiagrams.set(id, { lang: key.replace(/^kroki-/, ''), source: text });
      return `<div class="diagram-container" id="${id}"><div class="diagram-loading">Loading diagram...</div></div>`;
    }
    return false;
  }
};

marked.use({ renderer });

export function renderMd(text) {
  return { __html: marked.parse(text || '') };
}

export function renderDiagrams() {
  for (const [id, { lang, source }] of _pendingDiagrams) {
    const el = document.getElementById(id);
    if (!el) continue;
    fetch(`https://kroki.io/${lang}/svg`, {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain' },
      body: source,
    })
      .then(r => {
        if (!r.ok) throw new Error(`Kroki ${r.status}`);
        return r.text();
      })
      .then(svg => {
        const img = document.createElement('img');
        img.className = 'diagram-img';
        img.alt = `${lang} diagram`;
        img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
        el.replaceChildren(img);
      })
      .catch(() => {
        const err = document.createElement('div');
        err.className = 'diagram-error';
        err.textContent = `Failed to render ${lang} diagram`;
        el.replaceChildren(err);
      });
  }
  _pendingDiagrams.clear();
}
