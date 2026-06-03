import { h } from 'preact';
import { useRef, useEffect } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

export function SearchBar({ value, onChange, onClose, matchCount }) {
  const ref = useRef(null);

  useEffect(() => {
    if (ref.current) ref.current.focus();
  }, []);

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') onClose();
  };

  return html`
    <div class="search-bar">
      <span class="search-label">Search:</span>
      <input
        ref=${ref}
        class="search-input"
        type="text"
        value=${value}
        onInput=${(e) => onChange(e.target.value)}
        onKeyDown=${handleKeyDown}
        placeholder="Type to search..."
      />
      ${value && matchCount !== undefined && html`
        <span class="search-count">${matchCount} ${matchCount === 1 ? 'match' : 'matches'}</span>
      `}
      <button class="search-close-btn" onClick=${onClose}>✕</button>
    </div>
  `;
}
