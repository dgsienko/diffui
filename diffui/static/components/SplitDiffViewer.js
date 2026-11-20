import { h } from 'preact';
import { useState, useRef, useMemo } from 'preact/hooks';
import htm from 'htm';
import { CommentThread, LineCommentBox, SelectionCommentButton } from './CommentThread.js';
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

// Hunk headers and lines sit at the same index in both panes, but a comment thread
// or comment box takes room on one side only, so equal scrollTops drift apart below
// every thread. The target is scrolled to put the row at the top of the source pane
// at its own top, the same distance into it. While the source scrolls through a thread
// the other side lacks, the target waits at the start of the next row.
const ROWS = ':scope > .split-hunk-header, :scope > .split-line';

function lastRowAtOrAbove(rows, y) {
  let lo = 0;
  let hi = rows.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (rows[mid].offsetTop <= y) lo = mid;
    else hi = mid - 1;
  }
  return lo;
}

function alignedScrollTop(source, target) {
  const sourceRows = source.querySelectorAll(ROWS);
  const targetRows = target.querySelectorAll(ROWS);
  if (!sourceRows.length || sourceRows.length !== targetRows.length) return source.scrollTop;
  const sourceTop = source.scrollTop + sourceRows[0].offsetTop;
  const i = lastRowAtOrAbove(sourceRows, sourceTop);
  const into = sourceTop - sourceRows[i].offsetTop;
  const room = i + 1 < targetRows.length ? targetRows[i + 1].offsetTop - targetRows[i].offsetTop : Infinity;
  return targetRows[i].offsetTop - targetRows[0].offsetTop + Math.min(into, room);
}

function SplitLine({ line, side, onRightClick, commentRanges }) {
  if (!line) return html`<div class="split-line empty"></div>`;

  const typeClass = line.type === 'add' ? 'add' : line.type === 'remove' ? 'remove' : '';
  const num = side === 'left' ? line.old_num : line.new_num;
  const lineHtml = commentRanges && commentRanges.length ? highlightRanges(line.html, commentRanges) : line.html;

  return html`
    <div class=${'split-line ' + typeClass} data-line-index=${line.index} data-line-new=${side === 'right' ? line.new_num || undefined : undefined} onContextMenu=${(e) => { if (window.getSelection && window.getSelection().toString()) return; e.preventDefault(); onRightClick(line); }}>
      <span class="split-gutter">${num || ''}</span>
      <span class="split-code" dangerouslySetInnerHTML=${{ __html: lineHtml }}></span>
    </div>
  `;
}

export function SplitDiffViewer({ data, comments, actions, containerRef }) {
  const [commentingLine, setCommentingLine] = useState(null);
  const leftRef = useRef(null);
  const rightRef = useRef(null);
  // The position each pane was last scrolled to by syncScroll, so its own scroll
  // event is recognised as the echo and not synced back.
  const echo = useRef(new Map());
  const localContainerRef = useRef(null);
  const { selMenu, pendingSelection, setPendingSelection, commentFromSelection } = useRangeSelection('.split-code', localContainerRef, '.split-pane');

  const syncScroll = (sourceRef, targetRef) => {
    const source = sourceRef.current;
    const target = targetRef.current;
    if (!source || !target) return;
    const expected = echo.current.get(source);
    echo.current.delete(source);
    if (expected && expected.top === source.scrollTop && expected.left === source.scrollLeft) return;
    target.scrollTop = alignedScrollTop(source, target);
    target.scrollLeft = source.scrollLeft;
    echo.current.set(target, { top: target.scrollTop, left: target.scrollLeft });
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
      ...splitHunkLines(hunk.lines.filter(l => l.type !== 'meta')),
    }));
  }, [data]);

  if (!splitData) return html`<div class="empty-state">No diff data</div>`;

  return html`
    <div class="split-container" ref=${mergeRef(containerRef, localContainerRef)}>
      <${SelectionCommentButton} selMenu=${selMenu} onClick=${handleCommentSelection} />
      ${data.file_note && html`<div class="diff-file-note">${data.file_note}</div>`}
      <div class="split-panes">
        <div class="split-pane" ref=${leftRef} onScroll=${() => syncScroll(leftRef, rightRef)}>
          ${splitData.map(s => html`
            <div class="split-hunk-header">${s.header}</div>
            ${s.left.map(line => {
              const entry = entryFor(line);
              const lineComments = line && line.type === 'remove' ? entry.comments : [];
              return html`
                <${SplitLine} line=${line} side="left" onRightClick=${handleRightClick} commentRanges=${entry.ranges} />
                <${CommentThread} filePath=${data.file_path} comments=${lineComments} actions=${actions} />
                ${commentingLine === line?.index && line?.type === 'remove' && html`
                  <${LineCommentBox}
                    filePath=${data.file_path}
                    line=${line}
                    lineNum=${parseInt(line.old_num) || null}
                    selection=${selectionFor(line)}
                    actions=${actions}
                    onClose=${() => setCommentingLine(null)}
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
              <div class="split-hunk-header" aria-hidden="true">${"\u00a0"}</div>
              ${right.map((line, i) => {
                const entry = entryFor(line);
                return html`
                  <${SplitLine} line=${line} side="right" onRightClick=${handleRightClick} commentRanges=${entry.ranges} />
                  <${CommentThread} filePath=${data.file_path} comments=${entry.comments} actions=${actions} />
                  ${commentingLine === line?.index && line?.type !== 'remove' && html`
                    <${LineCommentBox}
                      filePath=${data.file_path}
                      line=${line}
                      lineNum=${parseInt(line.new_num) || parseInt(line.old_num) || null}
                      selection=${selectionFor(line)}
                      actions=${actions}
                      onClose=${() => setCommentingLine(null)}
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
