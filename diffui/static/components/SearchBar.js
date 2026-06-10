import { h } from 'preact';
import { useRef, useEffect } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

export function SearchBar({ value, onChange, onClose, matchCount, matchIndex, onNext, onPrev }) {
  const ref = useRef(null);

  useEffect(() => {
    if (ref.current) ref.current.focus();
  }, []);

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') onClose();
    if (e.key === 'Enter' && onNext) {
      e.preventDefault();
      if (e.shiftKey) { onPrev && onPrev(); }
      else { onNext(); }
    }
  };

  const hasValue = value && matchCount !== undefined;
  const noResults = hasValue && matchCount === 0;

  return html`
    <div class="search-bar">
      <span class="search-label">Search:</span>
      <input
        ref=${ref}
        class=${'search-input' + (noResults ? ' no-results' : '')}
        type="text"
        value=${value}
        onInput=${(e) => onChange(e.target.value)}
        onKeyDown=${handleKeyDown}
        placeholder="Type to search..."
      />
      ${hasValue && html`
        <span class="search-count">${matchCount > 0 && matchIndex !== undefined ? `${matchIndex + 1}/` : ''}${matchCount} ${matchCount === 1 ? 'match' : 'matches'}</span>
      `}
      ${matchCount > 0 && html`
        <button class="search-nav-btn" onClick=${onPrev} title="Previous match (Shift+Enter)">↑</button>
        <button class="search-nav-btn" onClick=${onNext} title="Next match (Enter)">↓</button>
      `}
      <button class="search-close-btn" onClick=${onClose} title="Close search (Escape)">✕</button>
    </div>
  `;
}
