import { h } from 'preact';
import { useState } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

function buildTree(files) {
  const tree = {};
  for (const f of files) {
    const parts = f.path.split('/');
    let node = tree;
    for (let i = 0; i < parts.length - 1; i++) {
      if (!node[parts[i]]) node[parts[i]] = { _files: [], _dirs: {} };
      node = node[parts[i]]._dirs;
    }
    const dir = parts.length > 1 ? parts.slice(0, -1).join('/') : '.';
    if (!tree._byDir) tree._byDir = {};
    if (!tree._byDir[dir]) tree._byDir[dir] = [];
    tree._byDir[dir].push(f);
  }
  return tree._byDir || {};
}

function TreeDir({ name, files, activeFile, onSelect }) {
  const [collapsed, setCollapsed] = useState(false);
  const commentCount = files.reduce((s, f) => s + (f.comment_count || 0), 0);
  const unreviewed = files.filter(f => !f.reviewed).length;

  return html`
    <div class="tree-dir">
      <div class="tree-dir-header" onClick=${() => setCollapsed(v => !v)}>
        <span class="tree-dir-arrow">${collapsed ? '▶' : '▼'}</span>
        <span class="tree-dir-name">${name}/</span>
        ${unreviewed > 0 && html`<span class="tree-badge">${unreviewed}</span>`}
        ${commentCount > 0 && html`<span class="tree-badge comment">${commentCount}</span>`}
      </div>
      ${!collapsed && html`
        <div class="tree-dir-files">
          ${files.map(f => html`
            <div
              class=${'tree-file' + (f.path === activeFile ? ' tree-active' : '') + (f.reviewed ? ' tree-reviewed' : '')}
              onClick=${() => onSelect(f.path)}
              title=${f.path}
            >
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
  const byDir = buildTree(files);
  const dirs = Object.keys(byDir).sort();

  return html`
    <div class="file-tree">
      <div class="file-tree-header">
        <span class="file-tree-title">Files</span>
        <button class="file-tree-close" onClick=${onClose}>✕</button>
      </div>
      <div class="file-tree-content">
        ${dirs.map(dir => html`
          <${TreeDir}
            key=${dir}
            name=${dir}
            files=${byDir[dir]}
            activeFile=${activeFile}
            onSelect=${onSelect}
          />
        `)}
      </div>
    </div>
  `;
}
