import { h } from 'preact';
import { useState, useRef } from 'preact/hooks';
import htm from 'htm';
import { CommentBox } from './CommentBox.js';
import { CommentDisplay } from './CommentDisplay.js';

const html = htm.bind(h);

function DiffLine({ line, searchTerm, onRightClick, onCtrlClick }) {
  const typeClass = {
    add: 'add',
    remove: 'remove',
    context: '',
    hunk: 'hunk-line',
    meta: 'meta',
  }[line.type] || '';

  const isMatch = searchTerm && line.text && line.text.toLowerCase().includes(searchTerm.toLowerCase());

  const handleClick = (e) => {
    if ((e.ctrlKey || e.metaKey) && line.new_num) {
      e.preventDefault();
      onCtrlClick(parseInt(line.new_num) || parseInt(line.old_num) || 1);
    }
  };

  const handleContext = (e) => {
    e.preventDefault();
    onRightClick(line);
  };

  // The HTML content is server-generated from Pygments (html.escape'd source code
  // in <span> tags). No user content is rendered as HTML — diff lines come from git
  // and are escaped server-side in highlight.py.
  return html`
    <div
      class=${'diff-line ' + typeClass + (isMatch ? ' search-match' : '')}
      onClick=${handleClick}
      onContextMenu=${handleContext}
    >
      <div class="diff-gutter">
        <span class="gutter-old">${line.old_num || ''}</span>
        <span class="gutter-sep">│</span>
        <span class="gutter-new">${line.new_num || ''}</span>
        <span class="gutter-sep">│</span>
      </div>
      <div class="diff-code" dangerouslySetInnerHTML=${{ __html: line.html }}></div>
    </div>
  `;
}

function Hunk({ hunk, comments, searchTerm, onRightClick, onCtrlClick, onAddComment, onDeleteComment, onEditComment, onReplyComment, commentingLine, setCommentingLine, filePath }) {
  const [collapsed, setCollapsed] = useState(false);

  return html`
    <div class="hunk">
      <div class="hunk-header" onClick=${() => setCollapsed(!collapsed)}>
        ${collapsed ? '▶' : '▼'} ${hunk.header}
      </div>
      <div class=${'hunk-lines' + (collapsed ? ' collapsed' : '')}>
        ${hunk.lines.map(line => {
          const lineComments = (comments[filePath] || []).filter(c => c.line_index === line.index);
          return html`
            <${DiffLine}
              key=${line.index}
              line=${line}
              searchTerm=${searchTerm}
              onRightClick=${onRightClick}
              onCtrlClick=${onCtrlClick}
            />
            ${lineComments.map(c => html`
              <${CommentDisplay}
                key=${c.id || (c.line_index + '-' + c.comment)}
                comment=${c}
                onDelete=${() => onDeleteComment(filePath, c.id)}
                onEdit=${(text) => onEditComment(filePath, c.id, text)}
                onReply=${(text) => onReplyComment(filePath, c.id, text)}
              />
            `)}
            ${commentingLine === line.index && html`
              <${CommentBox}
                onSubmit=${(text) => {
                  const lineNum = parseInt(line.new_num) || parseInt(line.old_num) || null;
                  onAddComment(filePath, line.index, line.text, lineNum, text);
                  setCommentingLine(null);
                }}
                onCancel=${() => setCommentingLine(null)}
              />
            `}
          `;
        })}
      </div>
    </div>
  `;
}

export function DiffViewer({ data, comments, searchTerm, onToggleReview, onAddComment, onDeleteComment, onEditComment, onReplyComment, onOpenInEditor, onExpandContext, contextLines, reviewed, ref }) {
  const [commentingLine, setCommentingLine] = useState(null);
  const containerRef = useRef(null);

  const handleRightClick = (line) => {
    setCommentingLine(line.index);
  };

  const handleCtrlClick = (lineNum) => {
    if (data?.file_path) onOpenInEditor(data.file_path, lineNum);
  };

  if (!data || !data.hunks) {
    return html`<div class="empty-state">No diff data</div>`;
  }

  const mergedRef = (el) => {
    containerRef.current = el;
    if (ref) ref.current = el;
  };

  return html`
    <div class="diff-container" ref=${mergedRef}>
      <div class="diff-file-header">
        <div>
          <span class="diff-file-path">${data.file_path}</span>
          <span class="diff-stat-add">+${data.adds}</span>
          <span class="diff-stat-del">-${data.dels}</span>
        </div>
        <div class="diff-header-actions">
          ${onExpandContext && contextLines < 9999 && html`
            <button class="expand-ctx-btn" onClick=${onExpandContext}>
              Expand context
            </button>
          `}
          <button class=${'review-btn' + (reviewed ? ' reviewed' : '')} onClick=${onToggleReview}>
            ${reviewed ? 'Mark unreviewed' : 'Mark reviewed'}
          </button>
        </div>
      </div>
      ${data.hunks.map((hunk, i) => html`
        <${Hunk}
          key=${i}
          hunk=${hunk}
          comments=${comments}
          searchTerm=${searchTerm}
          filePath=${data.file_path}
          commentingLine=${commentingLine}
          setCommentingLine=${setCommentingLine}
          onRightClick=${handleRightClick}
          onCtrlClick=${handleCtrlClick}
          onAddComment=${onAddComment}
          onDeleteComment=${onDeleteComment}
          onEditComment=${onEditComment}
          onReplyComment=${onReplyComment}
        />
      `)}
    </div>
  `;
}
