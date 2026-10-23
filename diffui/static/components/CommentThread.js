import { h } from 'preact';
import htm from 'htm';
import { CommentBox } from './CommentBox.js';
import { CommentDisplay } from './CommentDisplay.js';

const html = htm.bind(h);

// The comment handlers app.js passes to the diff viewers: onAddComment,
// onDeleteComment, onEditComment, onReplyComment, onResolveComment and
// onApplySuggestion.
export function CommentThread({ filePath, comments, actions }) {
  return comments.map(c => html`
    <${CommentDisplay}
      key=${c.id}
      comment=${c}
      onDelete=${() => actions.onDeleteComment(filePath, c.id)}
      onEdit=${(text) => actions.onEditComment(filePath, c.id, text)}
      onReply=${(text) => actions.onReplyComment(filePath, c.id, text)}
      onResolve=${() => actions.onResolveComment(filePath, c.id)}
      onApplySuggestion=${actions.onApplySuggestion}
    />
  `);
}

export function LineCommentBox({ filePath, line, lineNum, selection, actions, onClose }) {
  return html`
    <${CommentBox}
      lineText=${line.text}
      selectedText=${selection?.selectedText || ''}
      onSubmit=${(text, category, suggestion) => {
        actions.onAddComment(filePath, line.index, line.text, lineNum, text, category, suggestion, selection);
        onClose();
      }}
      onCancel=${onClose}
    />
  `;
}

export function SelectionCommentButton({ selMenu, onClick }) {
  if (!selMenu) return null;
  return html`
    <button
      class="selection-comment-btn"
      style=${{ left: selMenu.x + 'px', top: selMenu.y + 'px' }}
      onMouseDown=${(e) => e.preventDefault()}
      onClick=${onClick}
    >Comment</button>
  `;
}
