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

export function SettingsPanel({ onChange, onClose }) {
  const [settings, setSettings] = useState(null);
  const [themes, setThemes] = useState([]);
  const panelRef = useRef(null);

  useEffect(() => {
    fetch('/api/settings').then(r => r.json()).then(setSettings);
    fetch('/api/themes').then(r => r.json()).then(setThemes);
  }, []);

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

        <button class="settings-close-btn" onClick=${onClose}>Close</button>
      </div>
    </div>
  `;
}
