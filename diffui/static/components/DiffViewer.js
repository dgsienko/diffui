import { h } from 'preact';
import { useState, useRef } from 'preact/hooks';
import htm from 'htm';
import { CommentBox } from './CommentBox.js';
import { CommentDisplay } from './CommentDisplay.js';

const html = htm.bind(h);

function highlightSearch(html, term) {
  if (!term || !html) return html;
  const lowerTerm = term.toLowerCase();
  let result = '';
  let textBuf = '';
  let i = 0;
  const flushText = () => {
    if (!textBuf) return;
    const lower = textBuf.toLowerCase();
    let pos = 0;
    let idx;
    while ((idx = lower.indexOf(lowerTerm, pos)) !== -1) {
      result += textBuf.slice(pos, idx);
      result += '<mark class="search-hl">' + textBuf.slice(idx, idx + term.length) + '</mark>';
      pos = idx + term.length;
    }
    result += textBuf.slice(pos);
    textBuf = '';
  };
  while (i < html.length) {
    if (html[i] === '<') {
      flushText();
      const end = html.indexOf('>', i);
      if (end === -1) { result += html.slice(i); break; }
      result += html.slice(i, end + 1);
      i = end + 1;
    } else if (html[i] === '&') {
      flushText();
      const semi = html.indexOf(';', i);
      if (semi === -1) { result += html.slice(i); break; }
      result += html.slice(i, semi + 1);
      i = semi + 1;
    } else {
      textBuf += html[i];
      i++;
    }
  }
  flushText();
  return result;
}

function DiffLine({ line, searchTerm, onRightClick, onCtrlClick, onLineHover }) {
  const typeClass = {
    add: 'add',
    remove: 'remove',
    context: '',
    hunk: 'hunk-line',
    meta: 'meta',
  }[line.type] || '';

  const isMatch = searchTerm && line.text && line.text.toLowerCase().includes(searchTerm.toLowerCase());
  const lineHtml = isMatch ? highlightSearch(line.html, searchTerm) : line.html;

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
      onMouseEnter=${() => onLineHover && onLineHover(parseInt(line.new_num) || parseInt(line.old_num) || null)}
      onMouseLeave=${() => onLineHover && onLineHover(null)}
    >
      <div class="diff-gutter">
        <span class="gutter-old">${line.old_num || ''}</span>
        <span class="gutter-sep">│</span>
        <span class="gutter-new">${line.new_num || ''}</span>
        <span class="gutter-sep">│</span>
      </div>
      <div class="diff-code" dangerouslySetInnerHTML=${{ __html: lineHtml }}></div>
    </div>
  `;
}

function Hunk({ hunk, comments, searchTerm, onRightClick, onCtrlClick, onLineHover, onAddComment, onDeleteComment, onEditComment, onReplyComment, onResolveComment, commentingLine, setCommentingLine, filePath }) {
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
              onLineHover=${onLineHover}
            />
            ${lineComments.map(c => html`
              <${CommentDisplay}
                key=${c.id || (c.line_index + '-' + c.comment)}
                comment=${c}
                onDelete=${() => onDeleteComment(filePath, c.id)}
                onEdit=${(text) => onEditComment(filePath, c.id, text)}
                onReply=${(text) => onReplyComment(filePath, c.id, text)}
                onResolve=${() => onResolveComment(filePath, c.id)}
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

export function DiffViewer({ data, comments, searchTerm, onToggleReview, onAddComment, onDeleteComment, onEditComment, onReplyComment, onResolveComment, onOpenInEditor, onExpandContext, contextLines, onLineHover, reviewed, containerRef }) {
  const [commentingLine, setCommentingLine] = useState(null);

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
    if (containerRef) containerRef.current = el;
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
          ${onExpandContext && contextLines > 3 && html`
            <button class="expand-ctx-btn" onClick=${() => onExpandContext('collapse')}>
              Less context
            </button>
          `}
          ${onExpandContext && contextLines < 9999 && html`
            <button class="expand-ctx-btn" onClick=${() => onExpandContext('expand')}>
              More context
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
          onLineHover=${onLineHover}
          onAddComment=${onAddComment}
          onDeleteComment=${onDeleteComment}
          onEditComment=${onEditComment}
          onReplyComment=${onReplyComment}
          onResolveComment=${onResolveComment}
        />
      `)}
    </div>
  `;
}
