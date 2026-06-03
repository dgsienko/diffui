import { h } from 'preact';
import { useState, useEffect } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

const SPARKLES = ['✦', '✧', '·', '⋆', '˚'];

export function CompletionScreen({ fileCount, commentStats, onDismiss }) {
  const [sparkle, setSparkle] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setSparkle(s => (s + 1) % SPARKLES.length), 350);
    return () => clearInterval(id);
  }, []);

  const { total: totalComments, open: openComments } = commentStats || { total: 0, open: 0 };

  return html`
    <div class="completion-screen" onClick=${onDismiss}>
      <div class="completion-content">
        <div class="completion-sparkle">${SPARKLES[sparkle]}</div>
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
