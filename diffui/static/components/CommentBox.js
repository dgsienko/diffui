import { h } from 'preact';
import { useRef, useEffect } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

export function CommentBox({ onSubmit, onCancel }) {
  const ref = useRef(null);

  useEffect(() => {
    if (ref.current) ref.current.focus();
  }, []);

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      onCancel();
    } else if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      const text = ref.current.value.trim();
      if (text) onSubmit(text);
    }
  };

  const handleSubmit = () => {
    const text = ref.current.value.trim();
    if (text) onSubmit(text);
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
        <button class="comment-submit-btn" onClick=${handleSubmit}>Comment</button>
        <button class="comment-cancel-btn" onClick=${onCancel}>Cancel</button>
      </div>
    </div>
  `;
}
