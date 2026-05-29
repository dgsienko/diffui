import { h } from 'preact';
import { useMemo } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

export function TopBar({ repos, branch, commits, view, fileCount, reviewedCount, showReviewed, diffMode, comments, onViewChange, onDiffModeChange, onRepoSwitch, onToggleReviewed, onOpenSettings, onCommentSelect }) {
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

  const commentOptions = useMemo(() => {
    const opts = [];
    for (const [filePath, fileComments] of Object.entries(comments || {})) {
      const shortName = filePath.split('/').pop();
      for (const c of fileComments) {
        const label = fileComments.length > 1
          ? `${shortName} (line ${c.line_index})`
          : shortName;
        opts.push({ label, filePath, lineIndex: c.line_index });
      }
    }
    return opts;
  }, [comments]);

  return html`
    <div class="top-bar">
      <div class="top-bar-left">
        ${showRepoSelect && html`
          <select
            class="top-bar-select repo-select"
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
          value=${view}
          onChange=${(e) => onViewChange(e.target.value)}
        >
          ${viewOptions.map(o => html`
            <option value=${o.value}>${o.label}</option>
          `)}
        </select>
        <select
          class="top-bar-select comment-select"
          onChange=${(e) => {
            const idx = Number(e.target.value);
            if (idx >= 0 && commentOptions[idx]) {
              const opt = commentOptions[idx];
              onCommentSelect(opt.filePath, opt.lineIndex);
            }
            e.target.value = '';
          }}
          disabled=${!commentOptions.length}
        >
          <option value="">${commentOptions.length ? `Comments (${commentOptions.length})` : 'No comments'}</option>
          ${commentOptions.map((o, i) => html`
            <option value=${i}>${o.label}</option>
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
        <button class="top-bar-btn" onClick=${onToggleReviewed}>
          ${showReviewed ? 'Hide reviewed' : 'Show all'}
        </button>
        <span class="top-bar-badge">${reviewedCount}/${fileCount}</span>
      </div>
      <div class="top-bar-right">
        <span class="branch-pill">
          ${showRepoSelect && activeRepo ? html`<span class="branch-repo">${activeRepo.name}</span>` : ''}
          ${branch?.name || ''}
        </span>
        <button class="settings-btn" onClick=${onOpenSettings}>☰</button>
      </div>
    </div>
  `;
}
