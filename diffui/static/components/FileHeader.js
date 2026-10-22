import { h } from 'preact';
import htm from 'htm';
import { isPreviewable, previewLabel } from './PreviewViewer.js';

const html = htm.bind(h);

const MODES = [['unified', 'Unified'], ['split', 'Split'], ['file', 'File']];

function splitPath(path) {
  const i = path.lastIndexOf('/');
  return i === -1 ? ['', path] : [path.slice(0, i + 1), path.slice(i + 1)];
}

export function FileHeader({ activeFile, stats, reviewed, diffMode, onDiffModeChange, ignoreWhitespace, onToggleWhitespace, showReviewed, onToggleShowReviewed, showBlame, onToggleBlame, contextLines, onExpandContext, openCommentCount, onBulkResolve, onToggleReview, showPreview, onTogglePreview, keybindings }) {
  const kb = (id, fallback) => keybindings?.[id] || fallback;
  const [dir, name] = activeFile ? splitPath(activeFile) : ['', ''];
  const previewable = activeFile && isPreviewable(activeFile);
  const diffView = activeFile && diffMode === 'unified' && !(showPreview && previewable);

  return html`
    <div class="file-header">
      <div class="file-header-path">
        ${activeFile && html`
          <span class="file-path" title=${activeFile}>
            <span class="file-path-dir">${dir}</span><span class="file-path-name">${name}</span>
          </span>
          ${stats && html`
            <span class="file-header-stats">
              <span class="stats-add">+${stats.adds}</span>
              <span class="stats-del">−${stats.dels}</span>
            </span>
          `}
        `}
      </div>
      <div class="file-header-actions">
        <div class="mode-toggle">
          ${MODES.map(([val, label]) => html`
            <button class=${'mode-btn' + (diffMode === val ? ' active' : '')} onClick=${() => onDiffModeChange(val)} title=${label + ' diff view'}>${label}</button>
          `)}
        </div>
        <button class=${'btn' + (ignoreWhitespace ? ' active' : '')} onClick=${onToggleWhitespace} title="Toggle ignore whitespace (w)">
          Whitespace
        </button>
        <button class=${'btn' + (showReviewed ? '' : ' active')} onClick=${onToggleShowReviewed} title=${`${showReviewed ? 'Hide' : 'Show'} reviewed files (${kb('toggle-show-reviewed', 'a')})`}>
          ${showReviewed ? 'Hide reviewed' : 'Show all'}
        </button>
        ${previewable && html`
          <button class=${'btn' + (showPreview ? ' active' : '')} onClick=${onTogglePreview} title="Toggle rendered preview">
            ${showPreview ? 'Raw' : previewLabel(activeFile)}
          </button>
        `}
        ${diffView && html`
          <button class=${'btn' + (showBlame ? ' active' : '')} onClick=${onToggleBlame} title="Toggle git blame annotations">
            ${showBlame ? 'Hide blame' : 'Blame'}
          </button>
          ${contextLines > 3 && html`
            <button class="btn" onClick=${() => onExpandContext('collapse')} title="Show fewer context lines around changes">
              Less context
            </button>
          `}
          ${contextLines < 9999 && html`
            <button class="btn" onClick=${() => onExpandContext('expand')} title="Show more context lines around changes">
              More context
            </button>
          `}
          ${openCommentCount > 0 && html`
            <button class="btn" onClick=${onBulkResolve} title="Resolve all open comments in this file">
              Resolve all (${openCommentCount})
            </button>
          `}
        `}
        ${activeFile && (reviewed
          ? html`<button class="btn reviewed" onClick=${onToggleReview} title=${`Reviewed. Click to mark as unreviewed (${kb('toggle-review', 'r')})`}>Reviewed ✓</button>`
          : html`<button class="btn btn-primary" onClick=${onToggleReview} title=${`Mark as reviewed (${kb('toggle-review', 'r')})`}>Mark reviewed</button>`)}
      </div>
    </div>
  `;
}
