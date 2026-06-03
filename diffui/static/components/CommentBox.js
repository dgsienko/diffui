import { h } from 'preact';
import { useRef, useEffect, useState } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

const CATEGORIES = [
  { value: '', label: 'No category' },
  { value: 'bug', label: 'Bug' },
  { value: 'suggestion', label: 'Suggestion' },
  { value: 'nit', label: 'Nit' },
  { value: 'question', label: 'Question' },
];

export function CommentBox({ onSubmit, onCancel }) {
  const ref = useRef(null);
  const [category, setCategory] = useState('');

  useEffect(() => {
    if (ref.current) ref.current.focus();
  }, []);

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      onCancel();
    } else if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      const text = ref.current.value.trim();
      if (text) onSubmit(text, category);
    }
  };

  const handleSubmit = () => {
    const text = ref.current.value.trim();
    if (text) onSubmit(text, category);
  };

  return html`
    <div class="comment-box">
      <textarea
        ref=${ref}
        class="comment-input"
        placeholder="Add a comment... (Ctrl+Enter to submit)"
        onKeyDown=${handleKeyDown}
      ></textarea>
      <div class="comment-box-actions">
        <select class="comment-category-select" value=${category} onChange=${(e) => setCategory(e.target.value)}>
          ${CATEGORIES.map(c => html`<option value=${c.value}>${c.label}</option>`)}
        </select>
        <span class="comment-md-hint">Markdown supported</span>
        <button class="comment-submit-btn" onClick=${handleSubmit}>Comment</button>
        <button class="comment-cancel-btn" onClick=${onCancel}>Cancel</button>
      </div>
    </div>
  `;
}
