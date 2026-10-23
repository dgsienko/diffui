import { h } from 'preact';
import { useMemo } from 'preact/hooks';
import htm from 'htm';
import { shortName, useResize, isOpen } from '../lib/utils.js';

const html = htm.bind(h);

export function CommentsPanel({ comments, onSelect, onClose, onBulkResolve }) {
  const { ref: panelRef, size: width, onResizeStart } = useResize(300, 240, 400);

  const byFile = useMemo(() => {
    const map = {};
    for (const [filePath, fileComments] of Object.entries(comments)) {
      const open = fileComments.filter(isOpen);
      if (open.length) map[filePath] = open;
    }
    return map;
  }, [comments]);
  const openCount = useMemo(() => Object.values(byFile).reduce((n, list) => n + list.length, 0), [byFile]);

  return html`
    <div class="comments-panel" ref=${panelRef} style="width: ${width}px">
      <div class="comments-panel-header">
        <span class="comments-panel-title">${openCount} open comment${openCount === 1 ? '' : 's'}</span>
        <div style="display:flex;gap:4px;align-items:center">
          ${onBulkResolve && openCount > 0 && html`
            <button class="btn" onClick=${() => onBulkResolve(null)} title="Resolve all open comments">Resolve all</button>
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
        ${openCount === 0 && html`
          <div class="comments-panel-empty">No open comments</div>
        `}
      </div>
      <div class="comments-panel-resize" onMouseDown=${onResizeStart}></div>
    </div>
  `;
}
