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

// All HTML content is server-generated from Pygments output — source code is
// html.escape'd server-side in highlight.py before being wrapped in <span> tags.
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
