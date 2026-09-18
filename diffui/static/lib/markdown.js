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

const ALLOWED_TAGS = new Set([
  'p', 'br', 'hr', 'em', 'strong', 'del', 's', 'code', 'pre', 'blockquote',
  'ul', 'ol', 'li', 'a', 'img', 'span', 'div',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'table', 'thead', 'tbody', 'tr', 'th', 'td',
]);

// Unwrapping these would leave their source visible as text.
const DROP_WHOLE = new Set([
  'script', 'style', 'iframe', 'object', 'embed', 'link', 'meta', 'base',
  'form', 'input', 'button', 'textarea', 'select', 'noscript', 'template', 'svg', 'math',
]);

const ALLOWED_ATTRS = {
  a: ['href', 'title'],
  img: ['src', 'alt', 'title'],
  code: ['class'],
  div: ['class', 'id'],
  span: ['class'],
  th: ['align'],
  td: ['align'],
  ol: ['start'],
};

const SAFE_URL = /^(?:https?:|mailto:|#|\/|\.{0,2}\/|[\w.-]+[/?#]|data:image\/(?:png|jpeg|jpg|gif|webp);base64,)/i;

function sanitize(html) {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  for (const el of doc.body.querySelectorAll('*')) {
    const tag = el.tagName.toLowerCase();
    if (DROP_WHOLE.has(tag)) {
      el.remove();
      continue;
    }
    if (!ALLOWED_TAGS.has(tag)) {
      el.replaceWith(...el.childNodes);
      continue;
    }
    const allowed = ALLOWED_ATTRS[tag] || [];
    for (const { name, value } of [...el.attributes]) {
      if (!allowed.includes(name)) {
        el.removeAttribute(name);
      } else if ((name === 'href' || name === 'src') && !SAFE_URL.test(value.trim())) {
        el.removeAttribute(name);
      }
    }
  }
  return doc.body.innerHTML;
}

export function renderMd(text) {
  return { __html: sanitize(marked.parse(text || '')) };
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
