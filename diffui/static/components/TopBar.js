import { h } from 'preact';
import { useMemo } from 'preact/hooks';
import htm from 'htm';
import { isPreviewable } from './PreviewViewer.js';

const html = htm.bind(h);

export function TopBar({ repos, branch, commits, view, files, fileCount, reviewedCount, showReviewed, diffMode, comments, showPreview, onTogglePreview, activeFile, onViewChange, onDiffModeChange, onRepoSwitch, onToggleReviewed, onOpenSettings, onToggleCommentsPanel, agentRunning, onSendToAgent, onNextUnreviewed }) {
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
          <select class="top-bar-select repo-select" aria-label="Repository" onChange=${(e) => onRepoSwitch(Number(e.target.value))}>
            ${repos.map(r => html`<option value=${r.index} selected=${r.active}>${r.has_changes ? '● ' : '  '}${r.name}</option>`)}
          </select>
        `}
        <select class="top-bar-select view-select" aria-label="View filter" value=${view} onChange=${(e) => onViewChange(e.target.value)}>
          ${viewOptions.map(o => html`<option value=${o.value}>${o.label}</option>`)}
        </select>
        <span class="top-bar-stat"><span class="stats-add">+${totalAdds}</span> <span class="stats-del">−${totalDels}</span></span>
      </div>

      <div class="top-bar-center">
        <div class="mode-toggle">
          ${[['unified', 'U'], ['split', 'S'], ['file', 'F']].map(([val, label]) => html`
            <button class=${'mode-btn' + (diffMode === val ? ' active' : '')} onClick=${() => onDiffModeChange(val)} title=${{unified: 'Unified', split: 'Split', file: 'Full file'}[val]}>${label}</button>
          `)}
        </div>
        ${activeFile && isPreviewable(activeFile) && html`
          <button class=${'mode-btn' + (showPreview ? ' active' : '')} onClick=${onTogglePreview} title=${showPreview ? 'Show raw diff' : 'Preview rendered'}>P</button>
        `}
        <div class="top-bar-sep"></div>
        <div class="review-progress" title=${`${reviewedCount} of ${fileCount} files reviewed`}>
          <div class="progress-bar"><div class="progress-fill" style="width: ${progressPct}%"></div></div>
          <span class="progress-label">${reviewedCount}/${fileCount}</span>
        </div>
        ${reviewedCount < fileCount && html`
          <button class="top-bar-icon-btn" onClick=${onNextUnreviewed} title="Next unreviewed (])">▶</button>
        `}
        <button class="top-bar-icon-btn" onClick=${onToggleReviewed} title=${showReviewed ? 'Hide reviewed files' : 'Show all files'}>
          ${showReviewed ? '◉' : '○'}
        </button>
      </div>

      <div class="top-bar-right">
        ${openCommentCount > 0 && html`
          <button class="top-bar-icon-btn comment-count-btn" onClick=${onToggleCommentsPanel} title="Open comments panel">
            💬 ${openCommentCount}
          </button>
        `}
        ${onSendToAgent && html`
          <button
            class=${'top-bar-icon-btn agent-btn' + (agentRunning ? ' agent-running' : '')}
            onClick=${onSendToAgent}
            disabled=${agentRunning}
            title=${agentRunning ? 'Agent is running...' : 'Send comments to agent'}
          >${agentRunning ? '⟳' : '▷'}</button>
        `}
        <span class="branch-pill">
          ${showRepoSelect && activeRepo ? html`<span class="branch-repo">${activeRepo.name}</span>` : ''}
          ${branch?.name || ''}
        </span>
        <button class="settings-btn" onClick=${onOpenSettings} aria-label="Settings">⚙</button>
      </div>
    </div>
  `;
}
