import { h } from 'preact';
import { useState, useRef, useMemo } from 'preact/hooks';
import htm from 'htm';
import { CommentBox } from './CommentBox.js';
import { CommentDisplay } from './CommentDisplay.js';
import { mergeRef, highlightRanges, commentsByLine, NO_COMMENTS, useRangeSelection } from '../lib/utils.js';

const html = htm.bind(h);

function splitHunkLines(lines) {
  const left = [];
  const right = [];
  let removeBuffer = [];
  let addBuffer = [];

  const flush = () => {
    const count = Math.max(removeBuffer.length, addBuffer.length);
    for (let i = 0; i < count; i++) {
      left.push(removeBuffer[i] ?? null);
      right.push(addBuffer[i] ?? null);
    }
    removeBuffer = [];
    addBuffer = [];
  };

  for (const line of lines) {
    if (line.type === 'remove') {
      if (addBuffer.length) flush();
      removeBuffer.push(line);
    } else if (line.type === 'add') {
      addBuffer.push(line);
    } else {
      flush();
      left.push(line);
      right.push(line);
    }
  }
  flush();
  return { left, right };
}

// All HTML content is server-generated from Pygments output — source code is
// html.escape'd server-side in highlight.py before being wrapped in <span> tags.
function SplitLine({ line, side, onRightClick, commentRanges }) {
  if (!line) return html`<div class="split-line empty"></div>`;

  const typeClass = line.type === 'add' ? 'add' : line.type === 'remove' ? 'remove' : '';
  const num = side === 'left' ? line.old_num : line.new_num;
  const lineHtml = commentRanges && commentRanges.length ? highlightRanges(line.html, commentRanges) : line.html;

  return html`
    <div class=${'split-line ' + typeClass} data-line-index=${line.index} onContextMenu=${(e) => { if (window.getSelection && window.getSelection().toString()) return; e.preventDefault(); onRightClick(line); }}>
      <span class="split-gutter">${num || ''}</span>
      <span class="split-code" dangerouslySetInnerHTML=${{ __html: lineHtml }}></span>
    </div>
  `;
}

export function SplitDiffViewer({ data, comments, onToggleReview, onAddComment, onDeleteComment, onEditComment, onReplyComment, onResolveComment, onApplySuggestion, reviewed, containerRef }) {
  const [commentingLine, setCommentingLine] = useState(null);
  const leftRef = useRef(null);
  const rightRef = useRef(null);
  const syncing = useRef(false);
  const localContainerRef = useRef(null);
  const { selMenu, pendingSelection, setPendingSelection, commentFromSelection } = useRangeSelection('.split-code', localContainerRef, '.split-pane');

  const syncScroll = (source, target) => {
    if (syncing.current) return;
    syncing.current = true;
    requestAnimationFrame(() => {
      if (target.current) target.current.scrollTop = source.current.scrollTop;
      syncing.current = false;
    });
  };

  const handleRightClick = (line) => { setPendingSelection(null); setCommentingLine(line.index); };
  const handleCommentSelection = () => commentFromSelection(setCommentingLine);
  const selectionFor = (line) => (pendingSelection && line && pendingSelection.lineIndex === line.index ? pendingSelection : null);
  const byLine = useMemo(() => commentsByLine(comments[data?.file_path] || []), [comments, data?.file_path]);
  const entryFor = (line) => (line && byLine.get(line.index)) || NO_COMMENTS;

  const splitData = useMemo(() => {
    if (!data?.hunks) return null;
    return data.hunks.map(hunk => ({
      header: hunk.header,
      ...splitHunkLines(hunk.lines.filter(l => l.type !== 'hunk' && l.type !== 'meta')),
    }));
  }, [data]);

  if (!splitData) return html`<div class="empty-state">No diff data</div>`;

  return html`
    <div class="split-container" ref=${mergeRef(containerRef, localContainerRef)}>
      ${selMenu && html`
        <button
          class="selection-comment-btn"
          style=${{ left: selMenu.x + 'px', top: selMenu.y + 'px' }}
          onMouseDown=${(e) => e.preventDefault()}
          onClick=${handleCommentSelection}
        >💬 Comment</button>
      `}
      <div class="diff-file-header">
        <div>
          <span class="diff-file-path">${data.file_path}</span>
          <span class="diff-stat-add">+${data.adds}</span>
          <span class="diff-stat-del">-${data.dels}</span>
        </div>
        <button class=${'review-btn' + (reviewed ? ' reviewed' : '')} onClick=${onToggleReview}>
          ${reviewed ? 'Mark unreviewed' : 'Mark reviewed'}
        </button>
      </div>
      <div class="split-panes">
        <div class="split-pane" ref=${leftRef} onScroll=${() => syncScroll(leftRef, rightRef)}>
          ${splitData.map(s => html`
            <div class="split-hunk-header">${s.header}</div>
            ${s.left.map(line => {
              const entry = entryFor(line);
              const lineComments = line && line.type === 'remove' ? entry.comments : [];
              return html`
                <${SplitLine} line=${line} side="left" onRightClick=${handleRightClick} commentRanges=${entry.ranges} />
                ${lineComments.map(c => html`
                  <${CommentDisplay}
                    key=${c.id || c.line_index}
                    comment=${c}
                    onDelete=${() => onDeleteComment(data.file_path, c.id)}
                    onEdit=${(text) => onEditComment(data.file_path, c.id, text)}
                    onReply=${(text) => onReplyComment(data.file_path, c.id, text)}
                    onResolve=${() => onResolveComment(data.file_path, c.id)}
                    onApplySuggestion=${onApplySuggestion}
                  />
                `)}
                ${commentingLine === line?.index && line?.type === 'remove' && html`
                  <${CommentBox}
                    lineText=${line.text}
                    selectedText=${selectionFor(line)?.selectedText || ''}
                    onSubmit=${(text, category, suggestion) => {
                      const lineNum = parseInt(line.old_num) || null;
                      onAddComment(data.file_path, line.index, line.text, lineNum, text, category, suggestion, selectionFor(line));
                      setCommentingLine(null);
                    }}
                    onCancel=${() => setCommentingLine(null)}
                  />
                `}
              `;
            })}
          `)}
        </div>
        <div class="split-pane" ref=${rightRef} onScroll=${() => syncScroll(rightRef, leftRef)}>
          ${splitData.map(s => {
            const { right } = s;
            return html`
              <div class="split-hunk-header">${s.header}</div>
              ${right.map((line, i) => {
                const entry = entryFor(line);
                return html`
                  <${SplitLine} line=${line} side="right" onRightClick=${handleRightClick} commentRanges=${entry.ranges} />
                  ${entry.comments.map(c => html`
                    <${CommentDisplay}
                      key=${c.id || c.line_index}
                      comment=${c}
                      onDelete=${() => onDeleteComment(data.file_path, c.id)}
                      onEdit=${(text) => onEditComment(data.file_path, c.id, text)}
                      onReply=${(text) => onReplyComment(data.file_path, c.id, text)}
                      onResolve=${() => onResolveComment(data.file_path, c.id)}
                      onApplySuggestion=${onApplySuggestion}
                    />
                  `)}
                  ${commentingLine === line?.index && line?.type !== 'remove' && html`
                    <${CommentBox}
                      lineText=${line.text}
                      selectedText=${selectionFor(line)?.selectedText || ''}
                      onSubmit=${(text, category, suggestion) => {
                        const lineNum = parseInt(line.new_num) || parseInt(line.old_num) || null;
                        onAddComment(data.file_path, line.index, line.text, lineNum, text, category, suggestion, selectionFor(line));
                        setCommentingLine(null);
                      }}
                      onCancel=${() => setCommentingLine(null)}
                    />
                  `}
                `;
              })}
            `;
          })}
        </div>
      </div>
    </div>
  `;
}
