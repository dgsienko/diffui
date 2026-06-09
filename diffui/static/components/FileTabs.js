import { h } from 'preact';
import { useEffect, useRef } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

function tabDir(path) {
  const parts = path.split('/');
  return parts.length > 1 ? parts.slice(0, -1).join('/') + '/' : '';
}

export function FileTabs({ files, activeFile, onSelect, fileFilter, onFileFilterChange }) {
  const activeRef = useRef(null);

  useEffect(() => {
    if (activeRef.current) {
      activeRef.current.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    }
  }, [activeFile]);

  if (!files.length && !fileFilter) return null;

  return html`
    <div class="tab-bar-container">
      <div class="tab-bar" role="tablist">
        ${files.map(f => html`
          <div
            ref=${f.path === activeFile ? activeRef : null}
            class=${'tab' + (f.path === activeFile ? ' active' : '') + (f.reviewed ? ' reviewed' : '')}
            role="tab"
            tabindex=${f.path === activeFile ? '0' : '-1'}
            aria-selected=${f.path === activeFile}
            onClick=${() => onSelect(f.path)}
            onKeyDown=${(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(f.path); } }}
            title=${f.path}
          >
            ${f.risk_level && f.risk_level !== 'low' && html`<span class=${'risk-dot risk-' + f.risk_level} title=${'Risk: ' + f.risk_level}></span>`}
            ${f.reviewed ? '✓ ' : ''}
            ${f.path === activeFile && tabDir(f.path) ? html`<span class="tab-dir">${tabDir(f.path)}</span>` : ''}${f.short_name}
            ${f.comment_count > 0 ? html` <span style="color: var(--accent)">(${f.comment_count})</span>` : ''}
          </div>
        `)}
      </div>
      <input
        class="tab-filter"
        type="text"
        placeholder="Filter..."
        value=${fileFilter || ''}
        onInput=${(e) => onFileFilterChange(e.target.value)}
        aria-label="Filter files"
      />
    </div>
  `;
}
