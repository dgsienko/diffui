import { h } from 'preact';
import htm from 'htm';

const html = htm.bind(h);

export function LineActions({ onComment, onOpenInEditor }) {
  return html`
    <div class="line-actions">
      <button class="line-action-btn" onClick=${onComment} title="Add comment">+</button>
      ${onOpenInEditor && html`
        <button class="line-action-btn" onClick=${onOpenInEditor} title="Open in editor">↗</button>
      `}
    </div>
  `;
}
