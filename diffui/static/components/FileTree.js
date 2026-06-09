import { h } from 'preact';
import { useState } from 'preact/hooks';
import htm from 'htm';

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
    const ext = f.path.includes('.') ? '.' + f.path.rsplit ? f.path.split('.').pop() : f.path.split('.').pop() : 'other';
    const label = ext === 'other' ? 'Other' : `.${ext}`;
    if (!groups[label]) groups[label] = [];
    groups[label].push(f);
  }
  return groups;
}

function groupByStatus(files) {
  const groups = { modified: [], added: [], deleted: [] };
  for (const f of files) {
    if (f.adds > 0 && f.dels > 0) {
      groups.modified.push(f);
    } else if (f.adds > 0) {
      (groups.added || (groups.added = [])).push(f);
    } else {
      (groups.deleted || (groups.deleted = [])).push(f);
    }
  }
  return Object.fromEntries(Object.entries(groups).filter(([, v]) => v.length > 0));
}

const GROUP_MODES = [
  { value: 'dir', label: 'Dir' },
  { value: 'type', label: 'Type' },
  { value: 'status', label: 'Status' },
];

const GROUPERS = { dir: groupByDir, type: groupByType, status: groupByStatus };

function TreeDir({ name, files, activeFile, onSelect }) {
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
          ${files.map(f => html`
            <div
              class=${'tree-file' + (f.path === activeFile ? ' tree-active' : '') + (f.reviewed ? ' tree-reviewed' : '')}
              role="treeitem"
              tabindex="0"
              onClick=${() => onSelect(f.path)}
              onKeyDown=${(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(f.path); } }}
              title=${f.path}
            >
              ${f.risk_level && f.risk_level !== 'low' && html`<span class=${'risk-dot risk-' + f.risk_level}></span>`}
              ${f.reviewed ? '✓ ' : ''}${f.short_name}
              ${(f.comment_count || 0) > 0 && html`<span class="tree-comment-count">${f.comment_count}</span>`}
            </div>
          `)}
        </div>
      `}
    </div>
  `;
}

export function FileTree({ files, activeFile, onSelect, onClose }) {
  const [groupMode, setGroupMode] = useState('dir');
  const grouper = GROUPERS[groupMode] || groupByDir;
  const groups = grouper(files);
  const groupNames = Object.keys(groups).sort();

  return html`
    <div class="file-tree">
      <div class="file-tree-header">
        <span class="file-tree-title">Files</span>
        <div class="tree-group-toggle">
          ${GROUP_MODES.map(m => html`
            <button
              class=${'tree-group-btn' + (groupMode === m.value ? ' active' : '')}
              onClick=${() => setGroupMode(m.value)}
            >${m.label}</button>
          `)}
        </div>
        <button class="file-tree-close" onClick=${onClose}>✕</button>
      </div>
      <div class="file-tree-content">
        ${groupNames.map(name => html`
          <${TreeDir}
            key=${name}
            name=${name}
            files=${groups[name]}
            activeFile=${activeFile}
            onSelect=${onSelect}
          />
        `)}
      </div>
    </div>
  `;
}
