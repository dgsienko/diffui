import { h } from 'preact';
import htm from 'htm';

const html = htm.bind(h);

const SHORTCUTS = [
  { keys: '← →', action: 'Previous / next file' },
  { keys: 'j k', action: 'Next / previous hunk' },
  { keys: 'r', action: 'Toggle reviewed' },
  { keys: 'a', action: 'Show / hide reviewed' },
  { keys: 'n p', action: 'Next / previous comment' },
  { keys: 'y', action: 'Copy file path' },
  { keys: 'Y', action: 'Copy GitLab link' },
  { keys: ']', action: 'Next unreviewed file' },
  { keys: 's', action: 'Sort by risk' },
  { keys: 'b', action: 'Toggle explorer' },
  { keys: 'Ctrl+K', action: 'Command palette' },
  { keys: 'Ctrl+F', action: 'Search in diff' },
  { keys: 'Ctrl+Shift+F', action: 'Filter files' },
  { keys: 'Ctrl+Click', action: 'Open in editor' },
  { keys: 'c', action: 'Comment on hovered line' },
  { keys: 'Right-Click', action: 'Add comment' },
  { keys: 'Escape', action: 'Close panel / search' },
  { keys: '?', action: 'Toggle this overlay' },
];

export function ShortcutOverlay({ onClose }) {
  return html`
    <div class="shortcut-overlay" onClick=${(e) => { if (e.target.classList.contains('shortcut-overlay')) onClose(); }}>
      <div class="shortcut-panel">
        <div class="shortcut-title">Keyboard Shortcuts</div>
        <div class="shortcut-grid">
          ${SHORTCUTS.map(s => html`
            <div class="shortcut-keys">${s.keys.split(' ').map(k => html`<kbd>${k}</kbd> `)}</div>
            <div class="shortcut-action">${s.action}</div>
          `)}
        </div>
        <div class="shortcut-hint">Press <kbd>?</kbd> or <kbd>Escape</kbd> to close</div>
      </div>
    </div>
  `;
}
