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

function groupEntries(files, groupMode) {
  const groups = (GROUPERS[groupMode] || groupByDir)(files);
  return Object.keys(groups).sort().map(name => [name, groups[name]]);
}

// Files in the order the tree lists them, so prev/next file follows the sidebar.
// Sorting by risk drops the groups: the tree renders one flat list in this order.
export function treeOrder(files, groupMode, sortByRisk) {
  if (sortByRisk) return [...files].sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0));
  return groupEntries(files, groupMode).flatMap(([, group]) => group);
}

const RISK_TITLES = { medium: 'Medium risk', high: 'High risk' };

function TreeFiles({ files, activeFile, onSelect, commentsPulse }) {
  return files.map(f => {
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
        ${f.risk_level && f.risk_level !== 'low' && html`<span class=${'risk-dot risk-' + f.risk_level} title=${RISK_TITLES[f.risk_level]}></span>`}
        ${f.reviewed ? '✓ ' : ''}${f.short_name}
        ${hasComments && html`<span class="tree-comment-count">${f.comment_count}</span>`}
      </div>
    `;
  });
}

function TreeDir({ name, files, activeFile, onSelect, commentsPulse }) {
  const [collapsed, setCollapsed] = useState(false);

  return html`
    <div class="tree-dir">
      <div class="tree-dir-header" onClick=${() => setCollapsed(v => !v)}>
        <span class="tree-dir-arrow">${collapsed ? '▶' : '▼'}</span>
        <span class="tree-dir-name" title=${name}>${name}</span>
        <span class="tree-dir-count">${files.length}</span>
      </div>
      ${!collapsed && html`
        <div class="tree-dir-files">
          <${TreeFiles} files=${files} activeFile=${activeFile} onSelect=${onSelect} commentsPulse=${commentsPulse} />
        </div>
      `}
    </div>
  `;
}

export function FileTree({ files, activeFile, groupMode, sortByRisk, onGroupModeChange, onSelect, onClose, commentsPulse }) {
  const { ref: treeRef, size: width, onResizeStart } = useResize(260, 180, 500);

  return html`
    <div class="file-tree" ref=${treeRef} style="width: ${width}px">
      <div class="file-tree-header">
        <span class="file-tree-title">Files</span>
        ${!sortByRisk && html`
          <div class="segmented segmented-sm">
            ${GROUP_MODES.map(m => html`
              <button
                class=${'segmented-btn' + (groupMode === m.value ? ' active' : '')}
                onClick=${() => onGroupModeChange(m.value)}
                title=${m.title}
              >${m.label}</button>
            `)}
          </div>
        `}
        <button class="file-tree-close" onClick=${onClose} title="Close explorer">✕</button>
      </div>
      <div class="file-tree-content">
        ${sortByRisk
          ? html`<${TreeFiles} files=${files} activeFile=${activeFile} onSelect=${onSelect} commentsPulse=${commentsPulse} />`
          : groupEntries(files, groupMode).map(([name, group]) => html`
            <${TreeDir}
              key=${name}
              name=${name}
              files=${group}
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
