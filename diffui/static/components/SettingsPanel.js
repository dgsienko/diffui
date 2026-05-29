import { h } from 'preact';
import { useState, useEffect } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

const EDITORS = [
  { value: 'code', label: 'VS Code' },
  { value: 'cursor', label: 'Cursor' },
  { value: 'vim', label: 'Vim' },
  { value: 'nvim', label: 'Neovim' },
];

export function SettingsPanel({ onChange, onClose }) {
  const [settings, setSettings] = useState(null);
  const [themes, setThemes] = useState([]);

  useEffect(() => {
    fetch('/api/settings').then(r => r.json()).then(setSettings);
    fetch('/api/themes').then(r => r.json()).then(setThemes);
  }, []);

  if (!settings) return html`<div class="settings-panel"><div class="loading">Loading...</div></div>`;

  const update = async (changes) => {
    setSettings(s => ({ ...s, ...changes }));
    await onChange(changes);
  };

  return html`
    <div class="settings-overlay" onClick=${(e) => { if (e.target.classList.contains('settings-overlay')) onClose(); }}>
      <div class="settings-panel">
        <div class="settings-title">Settings</div>

        <label class="settings-label">Theme</label>
        <select
          class="settings-select"
          value=${settings.theme_index}
          onChange=${(e) => update({ theme_index: Number(e.target.value) })}
        >
          ${themes.map(t => html`<option value=${t.index}>${t.name}</option>`)}
        </select>

        <label class="settings-label">Editor</label>
        <select
          class="settings-select"
          value=${settings.editor}
          onChange=${(e) => update({ editor: e.target.value })}
        >
          ${EDITORS.map(e => html`<option value=${e.value}>${e.label}</option>`)}
        </select>

        <label class="settings-label">Display name</label>
        <input
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
