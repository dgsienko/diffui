import { h } from 'preact';
import { useState, useEffect } from 'preact/hooks';
import htm from 'htm';
import { renderMd } from '../lib/markdown.js';

const html = htm.bind(h);

const MD_EXTS = new Set(['md', 'markdown', 'mdx']);
// UI hint only — backend uses mimetypes.guess_type for authoritative detection
const IMG_EXTS = new Set(['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'ico', 'bmp', 'avif', 'tiff', 'tif']);

function getExt(path) {
  const dot = path.lastIndexOf('.');
  return dot >= 0 ? path.slice(dot + 1).toLowerCase() : '';
}

export function isPreviewable(path) {
  const ext = getExt(path);
  return MD_EXTS.has(ext) || IMG_EXTS.has(ext);
}

export function PreviewViewer({ filePath, onToggleReview, reviewed, containerRef }) {
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/preview/${encodeURIComponent(filePath)}`)
      .then(r => r.json())
      .then(d => { setPreview(d); setLoading(false); });
  }, [filePath]);

  const mergedRef = (el) => { if (containerRef) containerRef.current = el; };

  if (loading) return html`<div class="loading">Loading preview...</div>`;

  const ext = getExt(filePath);

  return html`
    <div class="diff-container preview-container" ref=${mergedRef}>
      <div class="diff-file-header">
        <div>
          <span class="diff-file-path">${filePath}</span>
          <span style="color: var(--fg-muted); margin-left: 12px">preview</span>
        </div>
        <button class=${'review-btn' + (reviewed ? ' reviewed' : '')} onClick=${onToggleReview}>
          ${reviewed ? 'Mark unreviewed' : 'Mark reviewed'}
        </button>
      </div>
      ${preview?.type === 'image' ? html`
        <div class="preview-image-container">
          ${preview.exists
            ? html`<img class="preview-image" src=${preview.data_url} alt=${filePath} />`
            : html`<div class="empty-state">Image file not found</div>`
          }
        </div>
      ` : MD_EXTS.has(ext) && preview?.content ? html`
        <div class="preview-markdown comment-md" dangerouslySetInnerHTML=${renderMd(preview.content)}></div>
      ` : html`
        <div class="empty-state">No preview available</div>
      `}
    </div>
  `;
}
