import { h } from 'preact';
import htm from 'htm';

const html = htm.bind(h);

export function TopBar({ repos, branch, commits, view, fileCount, reviewedCount, showReviewed, onViewChange, onRepoSwitch, onToggleReviewed, onOpenSettings }) {
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

  return html`
    <div class="top-bar">
      ${showRepoSelect && html`
        <select
          class="repo-select"
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
        class="view-select"
        value=${view}
        onChange=${(e) => onViewChange(e.target.value)}
      >
        ${viewOptions.map(o => html`
          <option value=${o.value}>${o.label}</option>
        `)}
      </select>
      <button class="top-bar-btn" onClick=${onToggleReviewed}>
        ${showReviewed ? 'Hide reviewed' : 'Show all'}
      </button>
      <span class="file-counter">${reviewedCount}/${fileCount} reviewed</span>
      <span class="branch-label">
        ${showRepoSelect && activeRepo ? `${activeRepo.name}: ` : ''}${branch?.name || ''}
      </span>
      <button class="settings-btn" onClick=${onOpenSettings}>☰</button>
    </div>
  `;
}
