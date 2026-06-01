import { h } from 'preact';
import { useState, useEffect, useRef, useMemo } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

export function CommandPalette({ commands, onExecute, onClose }) {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef(null);

  useEffect(() => {
    if (inputRef.current) inputRef.current.focus();
  }, []);

  const filtered = useMemo(() => {
    if (!query) return commands;
    const lower = query.toLowerCase();
    return commands.filter(c =>
      c.label.toLowerCase().includes(lower) ||
      (c.category && c.category.toLowerCase().includes(lower)) ||
      (c.keys && c.keys.toLowerCase().includes(lower))
    );
  }, [query, commands]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      onClose();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(i => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && filtered[selectedIndex]) {
      onExecute(filtered[selectedIndex].id);
      onClose();
    }
  };

  const { grouped, flatCommands } = useMemo(() => {
    const groups = {};
    const flat = [];
    for (const cmd of filtered) {
      const cat = cmd.category || 'Actions';
      if (!groups[cat]) groups[cat] = [];
      const entry = { ...cmd, flatIdx: flat.length };
      groups[cat].push(entry);
      flat.push(entry);
    }
    return { grouped: groups, flatCommands: flat };
  }, [filtered]);

  return html`
    <div class="command-palette-overlay" onClick=${(e) => { if (e.target.classList.contains('command-palette-overlay')) onClose(); }}>
      <div class="command-palette">
        <input
          ref=${inputRef}
          class="command-palette-input"
          type="text"
          placeholder="Type a command..."
          value=${query}
          onInput=${(e) => setQuery(e.target.value)}
          onKeyDown=${handleKeyDown}
        />
        <div class="command-palette-list">
          ${Object.entries(grouped).map(([category, cmds]) => html`
            <div class="command-palette-category">${category}</div>
            ${cmds.map(cmd => html`
              <div
                class=${'command-palette-item' + (cmd.flatIdx === selectedIndex ? ' selected' : '')}
                onClick=${() => { onExecute(cmd.id); onClose(); }}
                onMouseEnter=${() => setSelectedIndex(cmd.flatIdx)}
              >
                <span class="command-palette-label">${cmd.label}</span>
                ${cmd.keys && html`<span class="command-palette-keys">${cmd.keys}</span>`}
              </div>
            `)}
          `)}
          ${filtered.length === 0 && html`
            <div class="command-palette-empty">No matching commands</div>
          `}
        </div>
      </div>
    </div>
  `;
}
