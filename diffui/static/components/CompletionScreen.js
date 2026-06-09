import { h } from 'preact';
import htm from 'htm';

const html = htm.bind(h);

export function CompletionScreen({ fileCount, commentStats, onDismiss }) {
  const { total: totalComments, open: openComments } = commentStats || { total: 0, open: 0 };

  return html`
    <div class="completion-screen" onClick=${onDismiss}>
      <div class="completion-content">
        <div class="completion-check"></div>
        <div class="completion-title">Review Complete</div>
        <div class="completion-stats">
          <span class="completion-stat">${fileCount} ${fileCount === 1 ? 'file' : 'files'} reviewed</span>
          ${totalComments > 0 && html`
            <span class="completion-stat">${totalComments} ${totalComments === 1 ? 'comment' : 'comments'}</span>
          `}
          ${openComments > 0 && html`
            <span class="completion-stat open">${openComments} open</span>
          `}
        </div>
        <div class="completion-hint">Click anywhere or press any key to dismiss</div>
      </div>
    </div>
  `;
}
