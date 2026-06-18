import { h } from 'preact';
import { useState } from 'preact/hooks';
import htm from 'htm';
import { useResize } from '../lib/utils.js';

const html = htm.bind(h);

function groupByDir(files) {
  const groups = {};
  for (const f of files) {
    const parts = f.path.split('/');
    const dir = parts.length > 1 ? parts.slice(0, -1).join('/') : '.';
    if (!groups[dir]) groups[dir] = [];
    groups[dir].push(f);
  }
  return groups;
}

function groupByType(files) {
  const groups = {};
  for (const f of files) {
    const ext = f.path.includes('.') ? f.path.split('.').pop() : null;
    const label = ext ? `.${ext}` : 'Other';
    if (!groups[label]) groups[label] = [];
    groups[label].push(f);
  }
  return groups;
}

function groupByStatus(files) {
  const groups = {};
  for (const f of files) {
    const status = f.adds > 0 && f.dels > 0 ? 'modified' : f.dels > 0 ? 'deleted' : 'added';
    if (!groups[status]) groups[status] = [];
    groups[status].push(f);
  }
  return groups;
}

const GROUP_MODES = [
  { value: 'dir', label: 'Dir', title: 'Group by directory' },
  { value: 'type', label: 'Type', title: 'Group by file type' },
  { value: 'status', label: 'Status', title: 'Group by change status' },
];

const GROUPERS = { dir: groupByDir, type: groupByType, status: groupByStatus };

function TreeDir({ name, files, activeFile, onSelect, commentsPulse }) {
  const [collapsed, setCollapsed] = useState(false);
  const commentCount = files.reduce((s, f) => s + (f.comment_count || 0), 0);
  const unreviewed = files.filter(f => !f.reviewed).length;

  return html`
    <div class="tree-dir">
      <div class="tree-dir-header" onClick=${() => setCollapsed(v => !v)}>
        <span class="tree-dir-arrow">${collapsed ? '▶' : '▼'}</span>
        <span class="tree-dir-name">${name}</span>
        <span class="tree-dir-count">${files.length}</span>
        ${unreviewed > 0 && html`<span class="tree-badge">${unreviewed}</span>`}
        ${commentCount > 0 && html`<span class="tree-badge comment">${commentCount}</span>`}
      </div>
      ${!collapsed && html`
        <div class="tree-dir-files">
          ${files.map(f => {
            const hasComments = (f.comment_count || 0) > 0;
            const pulse = commentsPulse && hasComments && f.path !== activeFile;
            return html`
            <div
              class=${'tree-file' + (f.path === activeFile ? ' tree-active' : '') + (f.reviewed ? ' tree-reviewed' : '') + (pulse ? ' pulse-notify' : '')}
              role="treeitem"
              tabindex="0"
              onClick=${() => onSelect(f.path)}
              onKeyDown=${(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(f.path); } }}
              title=${f.path}
            >
              ${f.risk_level && f.risk_level !== 'low' && html`<span class=${'risk-dot risk-' + f.risk_level}></span>`}
              ${f.reviewed ? '✓ ' : ''}${f.short_name}
              ${hasComments && html`<span class="tree-comment-count">${f.comment_count}</span>`}
            </div>
          `;
          })}
        </div>
      `}
    </div>
  `;
}

export function FileTree({ files, activeFile, onSelect, onClose, commentsPulse }) {
  const [groupMode, setGroupMode] = useState('dir');
  const { ref: treeRef, size: width, onResizeStart } = useResize(260, 180, 500);
  const grouper = GROUPERS[groupMode] || groupByDir;
  const groups = grouper(files);
  const groupNames = Object.keys(groups).sort();

  return html`
    <div class="file-tree" ref=${treeRef} style="width: ${width}px">
      <div class="file-tree-header">
        <span class="file-tree-title">Files</span>
        <div class="tree-group-toggle">
          ${GROUP_MODES.map(m => html`
            <button
              class=${'tree-group-btn' + (groupMode === m.value ? ' active' : '')}
              onClick=${() => setGroupMode(m.value)}
              title=${m.title}
            >${m.label}</button>
          `)}
        </div>
        <button class="file-tree-close" onClick=${onClose} title="Close explorer">✕</button>
      </div>
      <div class="file-tree-content">
        ${groupNames.map(name => html`
          <${TreeDir}
            key=${name}
            name=${name}
            files=${groups[name]}
            activeFile=${activeFile}
            onSelect=${onSelect}
            commentsPulse=${commentsPulse}
          />
        `)}
      </div>
      <div class="file-tree-resize" onMouseDown=${onResizeStart}></div>
    </div>
  `;
}
