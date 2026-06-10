import { h } from 'preact';
import { useState, useEffect, useRef } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

const EDITORS = [
  { value: 'code', label: 'VS Code' },
  { value: 'cursor', label: 'Cursor' },
  { value: 'vim', label: 'Vim' },
  { value: 'nvim', label: 'Neovim' },
];

const AGENTS = [
  { value: 'claude', label: 'Claude Code' },
  { value: 'codex', label: 'Codex (OpenAI)' },
  { value: 'opencode', label: 'OpenCode' },
  { value: 'cursor', label: 'Cursor Agent' },
];

const REBINDABLE_KEYS = [
  { id: 'toggle-review', label: 'Toggle reviewed', default: 'r' },
  { id: 'toggle-show-reviewed', label: 'Show/hide reviewed', default: 'a' },
  { id: 'comment-line', label: 'Comment on line', default: 'c' },
  { id: 'copy-path', label: 'Copy file path', default: 'y' },
  { id: 'sort-risk', label: 'Sort by risk', default: 's' },
  { id: 'export-summary', label: 'Export summary', default: 'S' },
  { id: 'toggle-file-tree', label: 'Toggle explorer', default: 'b' },
  { id: 'next-unreviewed', label: 'Next unreviewed', default: ']' },
];

export function SettingsPanel({ onChange, onClose, fontSize, wordWrap, keybindings }) {
  const [settings, setSettings] = useState(null);
  const [themes, setThemes] = useState([]);
  const [showKeybindings, setShowKeybindings] = useState(false);
  const [localBindings, setLocalBindings] = useState(keybindings || {});
  const [capturingKey, setCapturingKey] = useState(null);
  const captureBtnRef = useRef(null);
  const panelRef = useRef(null);

  useEffect(() => {
    fetch('/api/settings').then(r => r.json()).then(setSettings);
    fetch('/api/themes').then(r => r.json()).then(setThemes);
  }, []);

  useEffect(() => {
    setLocalBindings(keybindings || {});
  }, [keybindings]);

  useEffect(() => {
    if (capturingKey && captureBtnRef.current) captureBtnRef.current.focus();
  }, [capturingKey]);

  useEffect(() => {
    const panel = panelRef.current;
    if (!panel) return;
    const focusable = panel.querySelectorAll('select, input, button, [tabindex]');
    if (focusable.length) focusable[0].focus();
    const trap = (e) => {
      if (e.key !== 'Tab' || !focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    panel.addEventListener('keydown', trap);
    return () => panel.removeEventListener('keydown', trap);
  }, [settings]);

  if (!settings) return html`<div class="settings-panel"><div class="loading">Loading...</div></div>`;

  const update = async (changes) => {
    setSettings(s => ({ ...s, ...changes }));
    await onChange(changes);
  };

  const handleKeyCapture = (e, keyId) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.key === 'Escape') {
      setCapturingKey(null);
      return;
    }
    if (e.key === 'Backspace') {
      const next = { ...localBindings };
      delete next[keyId];
      setLocalBindings(next);
      setCapturingKey(null);
      onChange({ keybindings: next });
      return;
    }
    if (e.key.length === 1 || e.key === '[' || e.key === ']') {
      const next = { ...localBindings, [keyId]: e.key };
      setLocalBindings(next);
      setCapturingKey(null);
      onChange({ keybindings: next });
    }
  };

  return html`
    <div class="settings-overlay" onClick=${(e) => { if (e.target.classList.contains('settings-overlay')) onClose(); }}>
      <div class="settings-panel" ref=${panelRef} role="dialog" aria-label="Settings">
        <div class="settings-title">Settings</div>

        <label class="settings-label" for="theme-select">Theme</label>
        <select
          id="theme-select"
          class="settings-select"
          value=${settings.theme_index}
          onChange=${(e) => update({ theme_index: Number(e.target.value) })}
        >
          ${themes.map(t => html`<option value=${t.index}>${t.name}</option>`)}
        </select>

        <label class="settings-label" for="editor-select">Editor</label>
        <select
          id="editor-select"
          class="settings-select"
          value=${settings.editor}
          onChange=${(e) => update({ editor: e.target.value })}
        >
          ${EDITORS.map(e => html`<option value=${e.value}>${e.label}</option>`)}
        </select>

        <label class="settings-label" for="agent-select">Agent CLI</label>
        <select
          id="agent-select"
          class="settings-select"
          value=${settings.agent_cli}
          onChange=${(e) => update({ agent_cli: e.target.value })}
        >
          ${AGENTS.map(a => html`<option value=${a.value}>${a.label}</option>`)}
        </select>

        <label class="settings-label" for="display-name">Display name</label>
        <input
          id="display-name"
          class="settings-input"
          value=${settings.user_name}
          onBlur=${(e) => {
            const name = e.target.value.trim();
            if (name && name !== settings.user_name) update({ user_name: name });
          }}
          onKeyDown=${(e) => { if (e.key === 'Enter') e.target.blur(); }}
        />

        <div class="settings-divider"></div>

        <label class="settings-label">Font size</label>
        <div class="settings-row">
          <button class="settings-btn-sm" onClick=${() => update({ font_size: Math.max((fontSize || 13) - 1, 8) })}>−</button>
          <span class="settings-value">${fontSize || 13}px</span>
          <button class="settings-btn-sm" onClick=${() => update({ font_size: Math.min((fontSize || 13) + 1, 24) })}>+</button>
        </div>

        <label class="settings-label">Word wrap</label>
        <div class="settings-row">
          <button class=${'settings-toggle' + (wordWrap ? ' active' : '')} onClick=${() => update({ word_wrap: !wordWrap })}>
            ${wordWrap ? 'On' : 'Off'}
          </button>
        </div>

        <div class="settings-divider"></div>

        <button class="settings-keybind-toggle" onClick=${() => setShowKeybindings(v => !v)}>
          ${showKeybindings ? '▾' : '▸'} Keybindings
        </button>

        ${showKeybindings && html`
          <div class="keybindings-list">
            ${REBINDABLE_KEYS.map(k => html`
              <div class="keybinding-row">
                <span class="keybinding-label">${k.label}</span>
                <button
                  ref=${capturingKey === k.id ? captureBtnRef : undefined}
                  class=${'keybinding-key' + (capturingKey === k.id ? ' capturing' : '')}
                  onClick=${() => setCapturingKey(capturingKey === k.id ? null : k.id)}
                  onKeyDown=${(e) => { if (capturingKey === k.id) handleKeyCapture(e, k.id); }}
                >
                  ${capturingKey === k.id ? 'Press key...' : html`<kbd>${localBindings[k.id] || k.default}</kbd>`}
                </button>
              </div>
            `)}
            <div class="keybinding-hint">Click a key to rebind. Backspace to reset. Escape to cancel.</div>
          </div>
        `}

        <button class="settings-close-btn" onClick=${onClose}>Close</button>
      </div>
    </div>
  `;
}
