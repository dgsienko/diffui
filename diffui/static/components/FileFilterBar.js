import { h } from 'preact';
import { useRef, useEffect } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

export function FileFilterBar({ value, onChange, onClose, fileCount }) {
  const ref = useRef(null);

  useEffect(() => {
    if (ref.current) ref.current.focus();
  }, []);

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') onClose();
  };

  return html`
    <div class="search-bar">
      <span class="search-label">Filter files:</span>
      <input
        ref=${ref}
        class="search-input"
        type="text"
        value=${value}
        onInput=${(e) => onChange(e.target.value)}
        onKeyDown=${handleKeyDown}
        placeholder="Type to filter by path..."
      />
      ${value && html`<span class="search-count">${fileCount} matching</span>`}
      <button class="search-close-btn" onClick=${onClose} title="Close filter (Escape)">✕</button>
    </div>
  `;
}
