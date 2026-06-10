import { h } from 'preact';
import { useState, useRef, useEffect, useCallback, useMemo } from 'preact/hooks';
import htm from 'htm';
import { CommentBox } from './CommentBox.js';
import { CommentDisplay } from './CommentDisplay.js';
import { LineActions } from './LineActions.js';
import { mergeRef } from '../lib/utils.js';

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

function BlameCell({ blame }) {
  if (!blame) return null;
  const now = Date.now() / 1000;
  const age = now - blame.timestamp;
  const days = Math.floor(age / 86400);
  const label = days < 1 ? 'today' : days < 30 ? `${days}d` : days < 365 ? `${Math.floor(days / 30)}mo` : `${Math.floor(days / 365)}y`;
  const name = (blame.author || '').split(' ')[0].slice(0, 8);
  return html`<span class="blame-cell" title=${blame.author + ' · ' + blame.sha}><span class="blame-name">${name}</span><span class="blame-age">${label}</span></span>`;
}

function DiffLine({ line, searchTerm, onRightClick, onCtrlClick, onOpenInEditor, onLineHover, blame }) {
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

  return html`
    <div
      class=${'diff-line ' + typeClass + (isMatch ? ' search-match' : '')}
      data-line-new=${line.new_num || undefined}
      onClick=${handleClick}
      onContextMenu=${handleContext}
      onMouseEnter=${() => onLineHover && onLineHover(line)}
      onMouseLeave=${() => onLineHover && onLineHover(null)}
    >
      ${blame && html`<${BlameCell} blame=${blame} />`}
      <div class="diff-gutter">
        <span class="gutter-old">${line.old_num || ''}</span>
        <span class="gutter-sep">│</span>
        <span class="gutter-new">${line.new_num || ''}</span>
        <span class="gutter-sep">│</span>
      </div>
      <div class="diff-code" dangerouslySetInnerHTML=${{ __html: lineHtml }}></div>
      ${line.type !== 'meta' && line.type !== 'hunk' && html`
        <${LineActions}
          onComment=${() => onRightClick(line)}
          onOpenInEditor=${onOpenInEditor && line.new_num ? () => onCtrlClick(parseInt(line.new_num) || 1) : null}
        />
      `}
    </div>
  `;
}

function hunkStats(lines) {
  let adds = 0, dels = 0;
  for (const l of lines) {
    if (l.type === 'add') adds++;
    else if (l.type === 'remove') dels++;
  }
  return { adds, dels };
}

function Hunk({ hunk, comments, searchTerm, onRightClick, onCtrlClick, onOpenInEditor, onLineHover, onAddComment, onDeleteComment, onEditComment, onReplyComment, onResolveComment, onApplySuggestion, commentingLine, setCommentingLine, filePath, blameData, collapseAll }) {
  const [collapsed, setCollapsed] = useState(false);
  const stats = useMemo(() => hunkStats(hunk.lines), [hunk.lines]);
  const lastCollapseVersion = useRef(0);

  useEffect(() => {
    if (collapseAll && collapseAll.version !== lastCollapseVersion.current) {
      lastCollapseVersion.current = collapseAll.version;
      setCollapsed(collapseAll.action === 'collapse');
    }
  }, [collapseAll]);

  return html`
    <div class="hunk">
      <div class="hunk-header" onClick=${() => setCollapsed(!collapsed)}>
        <span>${collapsed ? '▶' : '▼'} ${hunk.header}</span>
        <span class="hunk-stats">
          ${stats.adds > 0 ? html`<span class="hunk-stat-add">+${stats.adds}</span>` : ''}
          ${stats.dels > 0 ? html`<span class="hunk-stat-del">-${stats.dels}</span>` : ''}
        </span>
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
              onOpenInEditor=${onOpenInEditor}
              onLineHover=${onLineHover}
              blame=${blameData && line.new_num ? blameData[parseInt(line.new_num) - 1] : null}
            />
            ${lineComments.map(c => html`
              <${CommentDisplay}
                key=${c.id || (c.line_index + '-' + c.comment)}
                comment=${c}
                onDelete=${() => onDeleteComment(filePath, c.id)}
                onEdit=${(text) => onEditComment(filePath, c.id, text)}
                onReply=${(text) => onReplyComment(filePath, c.id, text)}
                onResolve=${() => onResolveComment(filePath, c.id)}
                onApplySuggestion=${onApplySuggestion}
              />
            `)}
            ${commentingLine === line.index && html`
              <${CommentBox}
                onSubmit=${(text, category) => {
                  const lineNum = parseInt(line.new_num) || parseInt(line.old_num) || null;
                  onAddComment(filePath, line.index, line.text, lineNum, text, category);
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

export function DiffViewer({ data, comments, searchTerm, onToggleReview, onAddComment, onDeleteComment, onEditComment, onReplyComment, onResolveComment, onApplySuggestion, onOpenInEditor, onExpandContext, contextLines, onLineHover, reviewed, containerRef, collapseAll, onBulkResolve }) {
  const [commentingLine, setCommentingLine] = useState(null);
  const [showBlame, setShowBlame] = useState(false);
  const [blameData, setBlameData] = useState(null);
  const blameCache = useRef(new Map());
  const hoveredLineRef = useRef(null);

  const fetchBlame = useCallback(async (filePath) => {
    const cached = blameCache.current.get(filePath);
    if (cached) { setBlameData(cached); return; }
    const res = await fetch(`/api/blame/${encodeURIComponent(filePath)}`);
    const result = await res.json();
    blameCache.current.set(filePath, result);
    setBlameData(result);
  }, []);

  useEffect(() => {
    if (showBlame && data?.file_path) {
      fetchBlame(data.file_path);
    } else {
      setBlameData(null);
    }
  }, [showBlame, data?.file_path, fetchBlame]);

  const handleRightClick = (line) => {
    setCommentingLine(line.index);
  };

  const handleLineHover = (line) => {
    hoveredLineRef.current = line;
    if (onLineHover) onLineHover(line ? (parseInt(line.new_num) || parseInt(line.old_num) || null) : null);
  };

  useEffect(() => {
    const handler = () => {
      const line = hoveredLineRef.current;
      if (line) setCommentingLine(line.index);
    };
    document.addEventListener('diffui:comment-on-hovered', handler);
    return () => document.removeEventListener('diffui:comment-on-hovered', handler);
  }, []);

  const handleCtrlClick = (lineNum) => {
    if (data?.file_path) onOpenInEditor(data.file_path, lineNum);
  };

  if (!data || !data.hunks) {
    return html`<div class="empty-state"><span class="empty-state-title">No diff data</span></div>`;
  }

  const fileCommentCount = (comments[data.file_path] || []).filter(c => (c.status || 'open') !== 'resolved').length;

  return html`
    <div class="diff-container" ref=${mergeRef(containerRef)}>
      <div class="diff-file-header">
        <div>
          <span class="diff-file-path">${data.file_path}</span>
          <span class="diff-stat-add">+${data.adds}</span>
          <span class="diff-stat-del">-${data.dels}</span>
        </div>
        <div class="diff-header-actions">
          <button class=${'expand-ctx-btn' + (showBlame ? ' active' : '')} onClick=${() => setShowBlame(v => !v)}>
            ${showBlame ? 'Hide blame' : 'Blame'}
          </button>
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
          ${onBulkResolve && fileCommentCount > 0 && html`
            <button class="expand-ctx-btn" onClick=${onBulkResolve} title="Resolve all open comments in this file">
              Resolve all (${fileCommentCount})
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
          onOpenInEditor=${onOpenInEditor ? handleCtrlClick : null}
          onLineHover=${handleLineHover}
          onAddComment=${onAddComment}
          onDeleteComment=${onDeleteComment}
          onEditComment=${onEditComment}
          onReplyComment=${onReplyComment}
          onResolveComment=${onResolveComment}
          onApplySuggestion=${onApplySuggestion}
          blameData=${showBlame ? blameData : null}
          collapseAll=${collapseAll}
        />
      `)}
    </div>
  `;
}
