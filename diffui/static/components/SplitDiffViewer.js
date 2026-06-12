import { h } from 'preact';
import { useState, useRef, useMemo } from 'preact/hooks';
import htm from 'htm';
import { CommentBox } from './CommentBox.js';
import { CommentDisplay } from './CommentDisplay.js';
import { mergeRef } from '../lib/utils.js';

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
function SplitLine({ line, side, onRightClick }) {
  if (!line) return html`<div class="split-line empty"></div>`;

  const typeClass = line.type === 'add' ? 'add' : line.type === 'remove' ? 'remove' : '';
  const num = side === 'left' ? line.old_num : line.new_num;

  return html`
    <div class=${'split-line ' + typeClass} onContextMenu=${(e) => { e.preventDefault(); onRightClick(line); }}>
      <span class="split-gutter">${num || ''}</span>
      <span class="split-code" dangerouslySetInnerHTML=${{ __html: line.html }}></span>
    </div>
  `;
}

export function SplitDiffViewer({ data, comments, onToggleReview, onAddComment, onDeleteComment, onEditComment, onReplyComment, onResolveComment, onApplySuggestion, reviewed, containerRef }) {
  const [commentingLine, setCommentingLine] = useState(null);
  const leftRef = useRef(null);
  const rightRef = useRef(null);
  const syncing = useRef(false);

  const syncScroll = (source, target) => {
    if (syncing.current) return;
    syncing.current = true;
    requestAnimationFrame(() => {
      if (target.current) target.current.scrollTop = source.current.scrollTop;
      syncing.current = false;
    });
  };

  const handleRightClick = (line) => setCommentingLine(line.index);

  const splitData = useMemo(() => {
    if (!data?.hunks) return null;
    return data.hunks.map(hunk => ({
      header: hunk.header,
      ...splitHunkLines(hunk.lines.filter(l => l.type !== 'hunk' && l.type !== 'meta')),
    }));
  }, [data]);

  if (!splitData) return html`<div class="empty-state">No diff data</div>`;

  return html`
    <div class="split-container" ref=${mergeRef(containerRef)}>
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
              const lineComments = line && line.type === 'remove' ? (comments[data.file_path] || []).filter(c => c.line_index === line.index) : [];
              return html`
                <${SplitLine} line=${line} side="left" onRightClick=${handleRightClick} />
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
                    onSubmit=${(text, category, suggestion) => {
                      const lineNum = parseInt(line.old_num) || null;
                      onAddComment(data.file_path, line.index, line.text, lineNum, text, category, suggestion);
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
                const lineComments = line ? (comments[data.file_path] || []).filter(c => c.line_index === line.index) : [];
                return html`
                  <${SplitLine} line=${line} side="right" onRightClick=${handleRightClick} />
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
                  ${commentingLine === line?.index && line?.type !== 'remove' && html`
                    <${CommentBox}
                      lineText=${line.text}
                      onSubmit=${(text, category, suggestion) => {
                        const lineNum = parseInt(line.new_num) || parseInt(line.old_num) || null;
                        onAddComment(data.file_path, line.index, line.text, lineNum, text, category, suggestion);
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
