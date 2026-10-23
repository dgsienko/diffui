import { h } from 'preact';
import { useState, useEffect, useRef, useMemo } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

export function CommandPalette({ commands, onExecute, onClose }) {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  useEffect(() => {
    if (inputRef.current) inputRef.current.focus();
  }, []);

  const moveSelection = (idx) => {
    setSelectedIndex(idx);
    const items = listRef.current.querySelectorAll('.command-palette-item');
    if (items[idx]) items[idx].scrollIntoView({ block: 'nearest' });
  };

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
      moveSelection(Math.min(selectedIndex + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      moveSelection(Math.max(selectedIndex - 1, 0));
    } else if (e.key === 'Enter' && filtered[selectedIndex]) {
      onExecute(filtered[selectedIndex].id);
      onClose();
    }
  };

  const grouped = useMemo(() => {
    const groups = {};
    let flatIdx = 0;
    for (const cmd of filtered) {
      const cat = cmd.category || 'Actions';
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push({ ...cmd, flatIdx: flatIdx++ });
    }
    return groups;
  }, [filtered]);

  return html`
    <div class="command-palette-overlay" onClick=${(e) => { if (e.target === e.currentTarget) onClose(); }}>
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
        <div class="command-palette-list" ref=${listRef}>
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
