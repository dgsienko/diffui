import { h } from 'preact';
import { useState, useRef } from 'preact/hooks';
import htm from 'htm';
import { marked } from 'marked';

marked.setOptions({ breaks: true, gfm: true });

const html = htm.bind(h);

function renderMd(text) {
  return { __html: marked.parse(text || '') };
}

export function CommentDisplay({ comment, onDelete, onEdit, onReply }) {
  const [showReply, setShowReply] = useState(false);
  const [editing, setEditing] = useState(false);
  const replyRef = useRef(null);
  const editRef = useRef(null);

  const isUser = comment.author_type === 'user';
  const icon = isUser ? '💬' : '🤖';
  const replies = comment.replies || [];
  const hasAgentReply = replies.some(r => (r.author_type || 'agent') !== 'user');
  const canEdit = isUser && !hasAgentReply;

  const handleReplySubmit = () => {
    const text = replyRef.current?.value.trim();
    if (text) {
      onReply(text);
      setShowReply(false);
    }
  };

  const handleEditSubmit = () => {
    const text = editRef.current?.value.trim();
    if (text && text !== comment.comment) {
      onEdit(text);
      setEditing(false);
    } else {
      setEditing(false);
    }
  };

  const handleKeyDown = (handler) => (e) => {
    if (e.key === 'Escape') { setShowReply(false); setEditing(false); }
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handler();
  };

  return html`
    <div class="comment-display">
      <div class="comment-header">
        <span class="comment-author">${icon} ${comment.author || 'User'}</span>
        <div class="comment-actions">
          <button class="comment-action-btn" onClick=${() => { setShowReply(true); setTimeout(() => replyRef.current?.focus(), 0); }}>↩</button>
          ${canEdit && html`
            <button class="comment-action-btn" onClick=${() => { setEditing(true); setTimeout(() => editRef.current?.focus(), 0); }}>✎</button>
          `}
          <button class="comment-action-btn delete" onClick=${onDelete}>✕</button>
        </div>
      </div>
      ${editing ? html`
        <div class="comment-edit-box">
          <textarea
            ref=${editRef}
            class="comment-reply-input"
            onKeyDown=${handleKeyDown(handleEditSubmit)}
          >${comment.comment}</textarea>
          <div class="comment-box-actions">
            <button class="comment-submit-btn" onClick=${handleEditSubmit}>Save</button>
            <button class="comment-cancel-btn" onClick=${() => setEditing(false)}>Cancel</button>
          </div>
        </div>
      ` : html`
        <div class="comment-body comment-md" dangerouslySetInnerHTML=${renderMd(comment.comment)}></div>
      `}
      ${replies.map(r => {
        const rIcon = (r.author_type || 'agent') === 'user' ? '💬' : '🤖';
        return html`
          <div class="comment-reply">↳ ${rIcon} ${r.author || 'agent'}: <span class="comment-md" dangerouslySetInnerHTML=${renderMd(r.text)}></span></div>
        `;
      })}
      ${showReply && html`
        <div class="comment-reply-box">
          <textarea
            ref=${replyRef}
            class="comment-reply-input"
            placeholder="Reply..."
            onKeyDown=${handleKeyDown(handleReplySubmit)}
          ></textarea>
          <div class="comment-box-actions">
            <button class="comment-submit-btn" onClick=${handleReplySubmit}>Reply</button>
            <button class="comment-cancel-btn" onClick=${() => setShowReply(false)}>Cancel</button>
          </div>
        </div>
      `}
    </div>
  `;
}
