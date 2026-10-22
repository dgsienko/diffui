import { h } from 'preact';
import { useMemo } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

export function TopBar({ repos, branch, commits, view, files, fileCount, reviewedCount, openCommentCount, onViewChange, onRepoSwitch, onOpenSettings, onToggleCommentsPanel, onToggleFileTree, onToggleFileFilter, showFileTree, showFileFilter, showCommentsPanel, agentRunning, onSendToAgent, explainRunning, onExplain, onShowShortcuts, wsConnected, keybindings, commentsPulse }) {
  const showRepoSelect = repos.length > 1;
  const kb = (id, fallback) => keybindings?.[id] || fallback;

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
    <div class="top-bar">
      <div class="top-bar-left">
        <button class=${'btn' + (showFileTree ? ' active' : '')} onClick=${onToggleFileTree} title=${`Toggle explorer (${kb('toggle-file-tree', 'b')})`}>
          Explorer
        </button>
        ${showRepoSelect && html`
          <select class="top-bar-select repo-select" aria-label="Repository" onChange=${(e) => onRepoSwitch(Number(e.target.value))}>
            ${repos.map(r => html`<option value=${r.index} selected=${r.active}>${r.has_changes ? '● ' : '  '}${r.name}</option>`)}
          </select>
        `}
        <span class="branch-name" title=${branch?.name || ''}>${branch?.name || ''}</span>
        <span
          class=${'connection-dot' + (wsConnected ? ' connected' : '')}
          role="img"
          aria-label=${wsConnected ? 'Live' : 'Offline'}
          title=${wsConnected ? 'Live: watching for changes' : 'Offline: reconnecting'}
        ></span>
        <select class="top-bar-select view-select" aria-label="View filter" value=${view} onChange=${(e) => onViewChange(e.target.value)}>
          ${viewOptions.map(o => html`<option value=${o.value}>${o.label}</option>`)}
        </select>
        <div class="review-progress" title=${`${reviewedCount} of ${fileCount} files reviewed`}>
          <div class="progress-bar"><div class="progress-fill" style="width: ${progressPct}%"></div></div>
          <span class="progress-label">${reviewedCount} of ${fileCount} reviewed · <span class="stats-add">+${totalAdds}</span> <span class="stats-del">−${totalDels}</span></span>
        </div>
      </div>
      <div class="top-bar-right">
        <button class=${'btn' + (showFileFilter ? ' active' : '')} onClick=${onToggleFileFilter} title="Search files (Ctrl+Shift+F)">
          Search files
        </button>
        <button class=${'btn' + (showCommentsPanel ? ' active' : '') + (commentsPulse && !showCommentsPanel ? ' pulse-notify' : '')} onClick=${onToggleCommentsPanel} title="Toggle comments panel">
          ${openCommentCount > 0 ? `Comments (${openCommentCount})` : 'Comments'}
        </button>
        ${onExplain && html`
          <button
            class="btn"
            onClick=${onExplain}
            disabled=${explainRunning}
            title="Generate an HTML walkthrough of all changes"
          >${explainRunning ? 'Generating...' : 'Explain changes'}</button>
        `}
        <button class="btn" onClick=${onShowShortcuts} title="Keyboard shortcuts (?)">? Shortcuts</button>
        <button class="btn" onClick=${onOpenSettings} title="Settings" aria-label="Settings">Settings</button>
        ${onSendToAgent && html`
          <button
            class=${'btn btn-primary' + (agentRunning ? ' agent-running' : '')}
            onClick=${onSendToAgent}
            disabled=${agentRunning}
            title="Send open comments to your configured agent CLI"
          >${agentRunning ? 'Agent running...' : 'Send to agent'}</button>
        `}
      </div>
    </div>
  `;
}
