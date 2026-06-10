import { h } from 'preact';
import { useState, useRef } from 'preact/hooks';
import htm from 'htm';
import { renderMd } from '../lib/markdown.js';

const html = htm.bind(h);

const AGENT_COLORS = [
  '#89b4fa', '#a6e3a1', '#cba6f7', '#fab387', '#f38ba8',
  '#94e2d5', '#f9e2af', '#89dceb', '#eba0ac', '#b4befe',
];

function agentColor(name) {
  let hash = 0;
  for (let i = 0; i < (name || '').length; i++) hash = ((hash << 5) - hash + name.charCodeAt(i)) | 0;
  return AGENT_COLORS[Math.abs(hash) % AGENT_COLORS.length];
}

export function CommentDisplay({ comment, onDelete, onEdit, onReply, onResolve, onApplySuggestion }) {
  const [showReply, setShowReply] = useState(false);
  const [editing, setEditing] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [applying, setApplying] = useState(false);
  const replyRef = useRef(null);
  const editRef = useRef(null);

  const isUser = comment.author_type === 'user';
  const authorStyle = !isUser ? { color: agentColor(comment.author) } : {};
  const replies = comment.replies || [];
  const hasAgentReply = replies.some(r => (r.author_type || 'agent') !== 'user');
  const canEdit = isUser && !hasAgentReply;
  const isResolved = comment.status === 'resolved';
  const category = comment.category || '';

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
    <div class=${'comment-display' + (isResolved ? ' comment-resolved' : '')}>
      <div class="comment-header">
        <span class="comment-author" style=${authorStyle}>
          ${comment.author || 'User'}
          ${category && html`<span class=${'comment-category-badge category-' + category}>${category}</span>`}
          ${isResolved && html`<span class="comment-status-badge resolved">Resolved</span>`}
        </span>
        <div class="comment-actions">
          ${replies.length > 0 && html`
            <button class="comment-action-btn" onClick=${() => setCollapsed(v => !v)} title=${collapsed ? 'Expand thread' : 'Collapse thread'}>
              ${collapsed ? '▸' : '▾'}
            </button>
          `}
          ${onResolve && html`
            <button class="comment-action-btn resolve" onClick=${onResolve} title=${isResolved ? 'Reopen' : 'Resolve'}>
              ${isResolved ? '○' : '✓'}
            </button>
          `}
          <button class="comment-action-btn" onClick=${() => { setShowReply(true); setTimeout(() => replyRef.current?.focus(), 0); }} title="Reply">↩</button>
          ${canEdit && html`
            <button class="comment-action-btn" onClick=${() => { setEditing(true); setTimeout(() => editRef.current?.focus(), 0); }} title="Edit">✎</button>
          `}
          <button class="comment-action-btn delete" onClick=${() => { if (confirm('Delete this comment?')) onDelete(); }} title="Delete">✕</button>
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
      ${comment.suggestion && html`
        <div class="comment-suggestion">
          <div class="comment-suggestion-header">
            <span>Suggested change</span>
            ${onApplySuggestion && !isResolved && html`
              <button
                class="comment-suggestion-apply"
                disabled=${applying}
                onClick=${async () => {
                  setApplying(true);
                  await onApplySuggestion(comment.file_path, comment.id);
                  setApplying(false);
                }}
              >${applying ? 'Applying...' : 'Apply'}</button>
            `}
          </div>
          ${comment.line_text ? html`
            <div class="suggestion-diff">
              <div class="suggestion-diff-line suggestion-remove">
                <span class="suggestion-diff-prefix">−</span>
                <span>${comment.line_text.trimEnd()}</span>
              </div>
              <div class="suggestion-diff-line suggestion-add">
                <span class="suggestion-diff-prefix">+</span>
                <span>${comment.suggestion.trimEnd()}</span>
              </div>
            </div>
          ` : html`
            <pre class="comment-suggestion-code">${comment.suggestion}</pre>
          `}
        </div>
      `}
      ${!collapsed && replies.map(r => {
        const rIsUser = (r.author_type || 'agent') === 'user';
        const rStyle = !rIsUser ? { color: agentColor(r.author) } : {};
        return html`
          <div class="comment-reply"><span style=${rStyle}>${r.author || 'agent'}</span>: <div class="comment-reply-md comment-md" dangerouslySetInnerHTML=${renderMd(r.text)}></div></div>
        `;
      })}
      ${collapsed && replies.length > 0 && html`
        <div class="comment-collapsed-hint">${replies.length} ${replies.length === 1 ? 'reply' : 'replies'} hidden</div>
      `}
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
