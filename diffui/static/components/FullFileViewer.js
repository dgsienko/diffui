import { h } from 'preact';
import { useState, useEffect } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

// All line HTML is server-generated from Pygments — source code is html.escape'd
// in highlight.py before wrapping in <span> tags. No user content is rendered as HTML.
export function FullFileViewer({ filePath, view, onToggleReview, reviewed, ref }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/file/${encodeURIComponent(filePath)}?view=${view}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); });
  }, [filePath, view]);

  if (loading) return html`<div class="loading">Loading...</div>`;
  if (!data?.lines?.length) return html`<div class="empty-state">File is empty</div>`;

  const mergedRef = (el) => { if (ref) ref.current = el; };

  return html`
    <div class="diff-container" ref=${mergedRef}>
      <div class="diff-file-header">
        <div>
          <span class="diff-file-path">${data.file_path}</span>
          <span style="color: var(--fg-muted); margin-left: 12px">${data.total_lines} lines</span>
          ${data.adds > 0 && html`<span class="diff-stat-add">+${data.adds}</span>`}
          ${data.dels > 0 && html`<span class="diff-stat-del">-${data.dels}</span>`}
        </div>
        <button class=${'review-btn' + (reviewed ? ' reviewed' : '')} onClick=${onToggleReview}>
          ${reviewed ? 'Mark unreviewed' : 'Mark reviewed'}
        </button>
      </div>
      ${data.lines.map(line => html`
        <div class=${'diff-line' + (line.type === 'add' ? ' add' : '')}>
          <div class="diff-gutter">
            <span class="gutter-new">${line.num}</span>
            <span class="gutter-sep">│</span>
          </div>
          <div class="diff-code" dangerouslySetInnerHTML=${{ __html: line.html }}></div>
        </div>
      `)}
    </div>
  `;
}
