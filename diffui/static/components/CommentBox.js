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

export function CommentBox({ onSubmit, onCancel, lineText, selectedText }) {
  const ref = useRef(null);
  const suggestionRef = useRef(null);
  const [category, setCategory] = useState('');

  useEffect(() => {
    if (ref.current) ref.current.focus();
  }, []);

  useEffect(() => {
    if (category === 'suggestion' && suggestionRef.current && !suggestionRef.current.value) {
      suggestionRef.current.value = lineText || '';
    }
  }, [category, lineText]);

  const submit = () => {
    const text = ref.current.value.trim();
    const suggestion = category === 'suggestion' && suggestionRef.current
      ? suggestionRef.current.value : '';
    if (!text && !suggestion) return;
    onSubmit(text || 'Suggested change', category, suggestion);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      onCancel();
    } else if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      submit();
    }
  };

  const handleCodeKeyDown = (e) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const ta = e.target;
      const start = ta.selectionStart;
      const end = ta.selectionEnd;
      ta.value = ta.value.substring(0, start) + '  ' + ta.value.substring(end);
      ta.selectionStart = ta.selectionEnd = start + 2;
    } else {
      handleKeyDown(e);
    }
  };

  return html`
    <div class="comment-box">
      ${selectedText && html`
        <div class="comment-box-selection" title="Commenting on selected text">
          <span class="comment-box-selection-label">On:</span>
          <code>${selectedText}</code>
        </div>
      `}
      <textarea
        ref=${ref}
        class="comment-input"
        placeholder=${category === 'suggestion'
          ? 'Explanation (optional)... (Ctrl+Enter to submit)'
          : 'Add a comment... (Ctrl+Enter to submit)'}
        onKeyDown=${handleKeyDown}
      ></textarea>
      ${category === 'suggestion' && html`
        <textarea
          ref=${suggestionRef}
          class="comment-input comment-suggestion-input"
          placeholder="Suggested replacement code..."
          onKeyDown=${handleCodeKeyDown}
          spellcheck=${false}
        ></textarea>
      `}
      <div class="comment-box-actions">
        <select class="comment-category-select" value=${category} onChange=${(e) => setCategory(e.target.value)}>
          ${CATEGORIES.map(c => html`<option value=${c.value}>${c.label}</option>`)}
        </select>
        <span class="comment-md-hint">Markdown supported</span>
        <button class="comment-submit-btn" onClick=${submit}>Comment</button>
        <button class="comment-cancel-btn" onClick=${onCancel}>Cancel</button>
      </div>
    </div>
  `;
}
