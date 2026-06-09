import { h } from 'preact';
import { useState, useEffect, useCallback, useRef } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

const LINE_HEIGHT = 20;
const OVERSCAN = 40;

// All line HTML is server-generated from Pygments — source code is html.escape'd
// in highlight.py before wrapping in <span> tags. No user content is rendered as HTML.
export function FullFileViewer({ filePath, view, onToggleReview, reviewed, containerRef }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(800);
  const scrollRef = useRef(null);
  const rafRef = useRef(0);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/file/${encodeURIComponent(filePath)}?view=${view}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); });
  }, [filePath, view]);

  const onScroll = useCallback(() => {
    cancelAnimationFrame(rafRef.current);
    rafRef.current = requestAnimationFrame(() => {
      const el = scrollRef.current;
      if (el) {
        setScrollTop(el.scrollTop);
        setViewportHeight(el.clientHeight);
      }
    });
  }, []);

  const mergedRef = useCallback((el) => {
    scrollRef.current = el;
    if (containerRef) containerRef.current = el;
    if (el) {
      setViewportHeight(el.clientHeight);
      el.addEventListener('scroll', onScroll, { passive: true });
    }
  }, [containerRef, onScroll]);

  useEffect(() => {
    return () => {
      const el = scrollRef.current;
      if (el) el.removeEventListener('scroll', onScroll);
      cancelAnimationFrame(rafRef.current);
    };
  }, [onScroll]);

  if (loading) return html`<div class="loading">Loading...</div>`;
  if (!data?.lines?.length) return html`<div class="empty-state"><span class="empty-state-title">File is empty</span></div>`;

  const headerHeight = 44;
  const totalLines = data.lines.length;
  const totalHeight = totalLines * LINE_HEIGHT;
  const adjustedScroll = Math.max(0, scrollTop - headerHeight);
  const startIdx = Math.max(0, Math.floor(adjustedScroll / LINE_HEIGHT) - OVERSCAN);
  const endIdx = Math.min(totalLines, Math.ceil((adjustedScroll + viewportHeight) / LINE_HEIGHT) + OVERSCAN);
  const offsetY = startIdx * LINE_HEIGHT;

  // Line HTML is Pygments-generated (escaped server-side in highlight.py)
  return html`
    <div class="diff-container" ref=${mergedRef}>
      <div class="diff-file-header">
        <div>
          <span class="diff-file-path">${data.file_path}</span>
          <span style="color: var(--fg-muted); margin-left: 12px">${data.total_lines} lines</span>
          ${data.adds > 0 && html`<span class="diff-stat-add">+${data.adds}</span>`}
          ${data.dels > 0 && html`<span class="diff-stat-del">-${data.dels}</span>`}
        </div>
        <button class=${'review-btn' + (reviewed ? ' reviewed' : '')} onClick=${onToggleReview}>
          ${reviewed ? 'Mark unreviewed' : 'Mark reviewed'}
        </button>
      </div>
      <div style="height: ${totalHeight}px; position: relative;">
        <div style="transform: translateY(${offsetY}px); will-change: transform;">
          ${data.lines.slice(startIdx, endIdx).map(line => html`
            <div key=${line.num} class=${'diff-line' + (line.type === 'add' ? ' add' : line.type === 'remove' ? ' remove' : '')} style="height: ${LINE_HEIGHT}px">
              <div class="diff-gutter">
                <span class="gutter-new">${line.num}</span>
                <span class="gutter-sep">│</span>
              </div>
              <div class="diff-code" dangerouslySetInnerHTML=${{ __html: line.html }}></div>
            </div>
          `)}
        </div>
      </div>
    </div>
  `;
}
