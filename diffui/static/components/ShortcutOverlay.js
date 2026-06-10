import { h } from 'preact';
import htm from 'htm';
import { mod } from '../lib/utils.js';

const html = htm.bind(h);

const SHORTCUTS = [
  { keys: '← →', action: 'Previous / next file' },
  { keys: 'j k', action: 'Next / previous hunk' },
  { id: 'toggle-review', keys: 'r', action: 'Toggle reviewed' },
  { id: 'toggle-show-reviewed', keys: 'a', action: 'Show / hide reviewed' },
  { keys: 'n p', action: 'Next / previous comment' },
  { id: 'copy-path', keys: 'y', action: 'Copy file path' },
  { keys: 'Y', action: 'Copy GitLab link' },
  { id: 'next-unreviewed', keys: ']', action: 'Next unreviewed file' },
  { id: 'sort-risk', keys: 's', action: 'Sort by risk' },
  { keys: 'w', action: 'Toggle ignore whitespace' },
  { id: 'toggle-file-tree', keys: 'b', action: 'Toggle explorer' },
  { keys: `${mod}+K`, action: 'Command palette' },
  { keys: 'Ctrl+F', action: 'Search in diff' },
  { keys: 'Ctrl+Shift+F', action: 'Filter files' },
  { keys: `${mod}+G`, action: 'Go to line' },
  { keys: `${mod}+Click`, action: 'Open in editor' },
  { id: 'comment-line', keys: 'c', action: 'Comment on hovered line' },
  { keys: 'Right-Click', action: 'Add comment' },
  { keys: 'Escape', action: 'Close panel / search' },
  { keys: '?', action: 'Toggle this overlay' },
];

export function ShortcutOverlay({ onClose, keybindings = {} }) {
  return html`
    <div class="shortcut-overlay" onClick=${(e) => { if (e.target.classList.contains('shortcut-overlay')) onClose(); }}>
      <div class="shortcut-panel">
        <div class="shortcut-title">Keyboard Shortcuts</div>
        <div class="shortcut-grid">
          ${SHORTCUTS.map(s => {
            const keys = (s.id && keybindings[s.id]) || s.keys;
            return html`
              <div class="shortcut-keys">${keys.split(' ').map(k => html`<kbd>${k}</kbd> `)}</div>
              <div class="shortcut-action">${s.action}</div>
            `;
          })}
        </div>
        <div class="shortcut-hint">Press <kbd>?</kbd> or <kbd>Escape</kbd> to close</div>
      </div>
    </div>
  `;
}
