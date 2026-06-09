import { h } from 'preact';
import { useMemo } from 'preact/hooks';
import htm from 'htm';
import { isPreviewable } from './PreviewViewer.js';

const html = htm.bind(h);

export function TopBar({ repos, branch, commits, view, files, fileCount, reviewedCount, showReviewed, diffMode, comments, showPreview, onTogglePreview, activeFile, onViewChange, onDiffModeChange, onRepoSwitch, onToggleReviewed, onOpenSettings, onToggleCommentsPanel, agentRunning, onSendToAgent, onNextUnreviewed, fileFilter, onFileFilterChange }) {
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
  const openCommentCount = useMemo(() => {
    let count = 0;
    for (const arr of Object.values(comments || {})) {
      count += arr.filter(c => (c.status || 'open') !== 'resolved').length;
    }
    return count;
  }, [comments]);

  const progressPct = fileCount > 0 ? (reviewedCount / fileCount) * 100 : 0;

  return html`
    <div class="top-bar">
      <div class="top-bar-left">
        ${showRepoSelect && html`
          <select
            class="top-bar-select repo-select"
            aria-label="Repository"
            onChange=${(e) => onRepoSwitch(Number(e.target.value))}
          >
            ${repos.map(r => html`
              <option value=${r.index} selected=${r.active}>
                ${r.has_changes ? '● ' : '  '}${r.name}
              </option>
            `)}
          </select>
        `}
        <select
          class="top-bar-select view-select"
          aria-label="View filter"
          value=${view}
          onChange=${(e) => onViewChange(e.target.value)}
        >
          ${viewOptions.map(o => html`
            <option value=${o.value}>${o.label}</option>
          `)}
        </select>
      </div>
      <div class="top-bar-center">
        <div class="mode-toggle">
          ${[['unified', 'Unified'], ['split', 'Split'], ['file', 'File']].map(([val, label]) => html`
            <button
              class=${'mode-btn' + (diffMode === val ? ' active' : '')}
              onClick=${() => onDiffModeChange(val)}
            >${label}</button>
          `)}
        </div>
        ${activeFile && isPreviewable(activeFile) && html`
          <button class=${'top-bar-btn' + (showPreview ? ' preview-active' : '')} onClick=${onTogglePreview}>
            ${showPreview ? 'Raw' : 'Preview'}
          </button>
        `}
        <button class="top-bar-btn" onClick=${onToggleReviewed}>
          ${showReviewed ? 'Hide reviewed' : 'Show all'}
        </button>
        <div class="review-progress" title=${`${reviewedCount} of ${fileCount} files reviewed`}>
          <span class="top-bar-badge">${reviewedCount}/${fileCount}</span>
          <div class="progress-bar">
            <div class="progress-fill" style="width: ${progressPct}%"></div>
          </div>
        </div>
        ${reviewedCount < fileCount && html`
          <button class="top-bar-btn next-unreviewed-btn" onClick=${onNextUnreviewed} title="Jump to next unreviewed file (])">▶</button>
        `}
      </div>
      <div class="top-bar-right">
        <div class="diff-stat-summary">
          <span class="stats-add">+${totalAdds}</span>
          <span class="stats-del">−${totalDels}</span>
        </div>
        ${openCommentCount > 0 && html`
          <button class="top-bar-btn comment-panel-btn" onClick=${onToggleCommentsPanel} title="Open comments panel">
            ${openCommentCount} comment${openCommentCount === 1 ? '' : 's'}
          </button>
        `}
        ${onSendToAgent && html`
          <button
            class=${'top-bar-btn agent-btn' + (agentRunning ? ' agent-running' : '')}
            onClick=${onSendToAgent}
            disabled=${agentRunning}
            title=${agentRunning ? 'Agent is running...' : 'Send open comments to agent'}
          >${agentRunning ? 'Agent running...' : 'Send to agent'}</button>
        `}
        <span class="branch-pill">
          ${showRepoSelect && activeRepo ? html`<span class="branch-repo">${activeRepo.name}</span>` : ''}
          ${branch?.name || ''}
        </span>
        <button class="settings-btn" onClick=${onOpenSettings} aria-label="Settings">⚙</button>
      </div>
    </div>
    <div class="sub-bar">
      <input
        class="file-filter-input"
        type="text"
        placeholder="Filter files..."
        value=${fileFilter || ''}
        onInput=${(e) => onFileFilterChange(e.target.value)}
        aria-label="Filter files by name"
      />
    </div>
  `;
}
