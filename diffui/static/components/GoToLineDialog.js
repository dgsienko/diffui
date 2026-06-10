import { h } from 'preact';
import { useRef, useEffect, useState } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

export function GoToLineDialog({ onSubmit, onClose }) {
  const [value, setValue] = useState('');
  const ref = useRef(null);

  useEffect(() => {
    if (ref.current) ref.current.focus();
  }, []);

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') onClose();
    if (e.key === 'Enter') {
      const num = parseInt(value, 10);
      if (num > 0) onSubmit(num);
    }
  };

  return html`
    <div class="goto-line-overlay" onClick=${(e) => { if (e.target.classList.contains('goto-line-overlay')) onClose(); }}>
      <div class="goto-line-dialog">
        <input
          ref=${ref}
          class="goto-line-input"
          type="number"
          min="1"
          placeholder="Go to line..."
          value=${value}
          onInput=${(e) => setValue(e.target.value)}
          onKeyDown=${handleKeyDown}
        />
      </div>
    </div>
  `;
}
