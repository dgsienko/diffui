import { h } from 'preact';
import htm from 'htm';
import { isPreviewable, previewLabel } from './PreviewViewer.js';
import { kb, shortName } from '../lib/utils.js';

const html = htm.bind(h);

const MODES = [['unified', 'Unified'], ['split', 'Split'], ['file', 'File']];

export function FileHeader({ activeFile, stats, reviewed, diffMode, onDiffModeChange, ignoreWhitespace, onToggleWhitespace, showReviewed, onToggleShowReviewed, showBlame, onToggleBlame, contextLines, onExpandContext, openCommentCount, onBulkResolve, onToggleReview, previewing, browsing, onTogglePreview, keybindings }) {
  const name = activeFile ? shortName(activeFile) : '';
  const dir = activeFile ? activeFile.slice(0, activeFile.length - name.length) : '';
  const previewable = activeFile && isPreviewable(activeFile);
  const diffView = activeFile && diffMode === 'unified' && !previewing;
  const reviewKey = kb(keybindings, 'toggle-review', 'r');

  if (browsing) {
    return html`
      <div class="file-header">
        <div class="file-header-path">
          <span class="file-path" title=${activeFile}>
            <span class="file-path-dir">${dir}</span><span class="file-path-name">${name}</span>
          </span>
          <span class="file-header-note">Not in diff, read only</span>
        </div>
      </div>
    `;
  }

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
        <div class="segmented">
          ${MODES.map(([val, label]) => html`
            <button class=${'segmented-btn' + (diffMode === val ? ' active' : '')} onClick=${() => onDiffModeChange(val)} title=${label + ' diff view'}>${label}</button>
          `)}
        </div>
        <button class=${'btn' + (ignoreWhitespace ? ' active' : '')} onClick=${onToggleWhitespace} title="Toggle ignore whitespace (w)">
          Whitespace
        </button>
        <button class=${'btn' + (showReviewed ? '' : ' active')} onClick=${onToggleShowReviewed} title=${`${showReviewed ? 'Hide' : 'Show'} reviewed files (${kb(keybindings, 'toggle-show-reviewed', 'a')})`}>
          ${showReviewed ? 'Hide reviewed' : 'Show all'}
        </button>
        ${previewable && html`
          <button class=${'btn' + (previewing ? ' active' : '')} onClick=${onTogglePreview} title="Toggle rendered preview">
            ${previewing ? 'Raw' : previewLabel(activeFile)}
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
        ${activeFile && html`
          <button
            class=${'btn ' + (reviewed ? 'reviewed' : 'btn-primary')}
            onClick=${onToggleReview}
            title=${(reviewed ? 'Reviewed. Click to mark as unreviewed' : 'Mark as reviewed') + ` (${reviewKey})`}
          >${reviewed ? 'Reviewed ✓' : 'Mark reviewed'}</button>
        `}
      </div>
    </div>
  `;
}
