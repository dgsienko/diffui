import { h } from 'preact';
import { useMemo } from 'preact/hooks';
import htm from 'htm';
import { isPreviewable } from './PreviewViewer.js';

const html = htm.bind(h);

export function TopBar({ repos, branch, commits, view, files, fileCount, reviewedCount, showReviewed, diffMode, openCommentCount, showPreview, onTogglePreview, activeFile, onViewChange, onDiffModeChange, onRepoSwitch, onToggleReviewed, onOpenSettings, onToggleCommentsPanel, onToggleFileTree, onToggleFileFilter, showFileTree, showFileFilter, agentRunning, onSendToAgent }) {
  const activeRepo = repos.find(r => r.active);
  const showRepoSelect = repos.length > 1;

  const viewOptions = [
    { value: 'all', label: 'All changes' },
    { value: 'working', label: 'Working changes (uncommitted)' },
    ...(commits || []).map(c => ({
      value: c.sha,
      label: c.message.slice(0, 50),
    })).reverse(),
  ];

  const totalAdds = useMemo(() => (files || []).reduce((s, f) => s + (f.adds || 0), 0), [files]);
  const totalDels = useMemo(() => (files || []).reduce((s, f) => s + (f.dels || 0), 0), [files]);

  const progressPct = fileCount > 0 ? (reviewedCount / fileCount) * 100 : 0;

  return html`
    <div class="top-bar-wrapper">
      <div class="top-bar">
        <div class="top-bar-left">
          ${showRepoSelect && html`
            <select class="top-bar-select repo-select" aria-label="Repository" onChange=${(e) => onRepoSwitch(Number(e.target.value))}>
              ${repos.map(r => html`<option value=${r.index} selected=${r.active}>${r.has_changes ? '● ' : '  '}${r.name}</option>`)}
            </select>
          `}
          <select class="top-bar-select view-select" aria-label="View filter" value=${view} onChange=${(e) => onViewChange(e.target.value)}>
            ${viewOptions.map(o => html`<option value=${o.value}>${o.label}</option>`)}
          </select>
        </div>
        <div class="top-bar-right">
          <span class="branch-pill">
            ${showRepoSelect && activeRepo ? html`<span class="branch-repo">${activeRepo.name}</span>` : ''}
            ${branch?.name || ''}
          </span>
          <button class="settings-btn" onClick=${onOpenSettings} aria-label="Settings">⚙</button>
        </div>
      </div>
      <div class="toolbar">
        <div class="toolbar-left">
          <div class="mode-toggle">
            ${[['unified', 'Unified'], ['split', 'Split'], ['file', 'File']].map(([val, label]) => html`
              <button class=${'mode-btn' + (diffMode === val ? ' active' : '')} onClick=${() => onDiffModeChange(val)}>${label}</button>
            `)}
          </div>
          ${activeFile && isPreviewable(activeFile) && html`
            <button class=${'toolbar-btn' + (showPreview ? ' preview-active' : '')} onClick=${onTogglePreview}>
              ${showPreview ? 'Raw' : 'Preview'}
            </button>
          `}
          <button class="toolbar-btn" onClick=${onToggleReviewed}>
            ${showReviewed ? 'Hide reviewed' : 'Show all'}
          </button>
        </div>
        <div class="toolbar-center">
          <div class="review-progress" title=${`${reviewedCount} of ${fileCount} files reviewed`}>
            <div class="progress-bar"><div class="progress-fill" style="width: ${progressPct}%"></div></div>
            <span class="progress-label">${reviewedCount}/${fileCount}</span>
          </div>
          <span class="toolbar-stat"><span class="stats-add">+${totalAdds}</span> <span class="stats-del">−${totalDels}</span></span>
        </div>
        <div class="toolbar-right">
          <button class=${'toolbar-btn panel-toggle' + (showFileTree ? ' panel-active' : '')} onClick=${onToggleFileTree} title="Toggle explorer (b)">
            Explorer
          </button>
          <button class=${'toolbar-btn panel-toggle' + (showFileFilter ? ' panel-active' : '')} onClick=${onToggleFileFilter} title="Search files (Ctrl+Shift+F)">
            Search files
          </button>
          ${openCommentCount > 0 && html`
            <button class="toolbar-btn" onClick=${onToggleCommentsPanel}>
              ${openCommentCount} comment${openCommentCount === 1 ? '' : 's'}
            </button>
          `}
          ${onSendToAgent && html`
            <button
              class=${'toolbar-btn agent-btn' + (agentRunning ? ' agent-running' : '')}
              onClick=${onSendToAgent}
              disabled=${agentRunning}
            >${agentRunning ? 'Agent running...' : 'Send to agent'}</button>
          `}
        </div>
      </div>
    </div>
  `;
}
