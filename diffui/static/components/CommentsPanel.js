import { h } from 'preact';
import { useMemo } from 'preact/hooks';
import htm from 'htm';
import { shortName } from '../lib/utils.js';

const html = htm.bind(h);

export function CommentsPanel({ comments, onSelect, onClose, onBulkResolve }) {
  const allComments = useMemo(() => {
    const result = [];
    for (const [filePath, fileComments] of Object.entries(comments || {})) {
      for (const c of fileComments) {
        if ((c.status || 'open') !== 'resolved') {
          result.push({ ...c, _file: filePath });
        }
      }
    }
    return result;
  }, [comments]);

  const byFile = useMemo(() => {
    const map = {};
    for (const c of allComments) {
      if (!map[c._file]) map[c._file] = [];
      map[c._file].push(c);
    }
    return map;
  }, [allComments]);

  return html`
    <div class="comments-panel">
      <div class="comments-panel-header">
        <span class="comments-panel-title">${allComments.length} open comment${allComments.length === 1 ? '' : 's'}</span>
        <div style="display:flex;gap:4px;align-items:center">
          ${onBulkResolve && allComments.length > 0 && html`
            <button class="expand-ctx-btn" onClick=${() => onBulkResolve(null)} title="Resolve all open comments">Resolve all</button>
          `}
          <button class="file-tree-close" onClick=${onClose} title="Close comments panel">✕</button>
        </div>
      </div>
      <div class="comments-panel-content">
        ${Object.entries(byFile).map(([filePath, fileComments]) => html`
          <div class="comments-panel-file">
            <div class="comments-panel-filename">${shortName(filePath)}</div>
            ${fileComments.map(c => {
              const lineNum = c.file_line_num || c.line_index || '?';
              const cat = c.category || '';
              return html`
                <div
                  class="comments-panel-item"
                  onClick=${() => { onSelect(filePath, lineNum); onClose(); }}
                >
                  <span class="comments-panel-line">:${lineNum}</span>
                  ${cat && html`<span class=${'comment-category-badge category-' + cat}>${cat}</span>`}
                  <span class="comments-panel-text">${c.comment?.slice(0, 80)}${c.comment?.length > 80 ? '...' : ''}</span>
                </div>
              `;
            })}
          </div>
        `)}
        ${allComments.length === 0 && html`
          <div class="comments-panel-empty">No open comments</div>
        `}
      </div>
    </div>
  `;
}
