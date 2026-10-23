import { h } from 'preact';
import { useState, useEffect, useCallback, useRef } from 'preact/hooks';
import htm from 'htm';
import { mergeRef } from '../lib/utils.js';

const html = htm.bind(h);

const LINE_HEIGHT = 20;
const OVERSCAN = 40;

// All line HTML is server-generated from Pygments: source code is html.escape'd
// in highlight.py before wrapping in <span> tags. No user content is rendered as HTML.
export function FullFileViewer({ filePath, view, containerRef, gotoLine, readOnly }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(800);
  const scrollRef = useRef(null);
  const rafRef = useRef(0);

  useEffect(() => {
    let stale = false;
    setLoading(true);
    fetch(`/api/file/${encodeURIComponent(filePath)}?view=${view}`)
      .then(r => r.json())
      .then(d => { if (!stale) { setData(d); setLoading(false); } });
    return () => { stale = true; };
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

  useEffect(() => {
    const el = scrollRef.current;
    if (!el || !data) return;
    setViewportHeight(el.clientHeight);
    if (gotoLine) el.scrollTop = Math.max(0, (gotoLine - 1) * LINE_HEIGHT - el.clientHeight / 2);
  }, [data, gotoLine]);

  useEffect(() => () => cancelAnimationFrame(rafRef.current), []);

  if (loading) return html`<div class="loading">Loading...</div>`;
  if (!data?.lines?.length) return html`<div class="empty-state"><span class="empty-state-title">File is empty</span></div>`;

  const totalLines = data.lines.length;
  const totalHeight = totalLines * LINE_HEIGHT;
  const startIdx = Math.max(0, Math.floor(scrollTop / LINE_HEIGHT) - OVERSCAN);
  const endIdx = Math.min(totalLines, Math.ceil((scrollTop + viewportHeight) / LINE_HEIGHT) + OVERSCAN);
  const offsetY = startIdx * LINE_HEIGHT;

  return html`
    <div class="diff-container" ref=${mergeRef(scrollRef, containerRef)} onScroll=${onScroll}>
      <div style="height: ${totalHeight}px; position: relative;">
        <div style="transform: translateY(${offsetY}px); will-change: transform;">
          ${data.lines.slice(startIdx, endIdx).map(line => html`
            <div key=${line.num} class=${'diff-line' + (readOnly ? '' : line.type === 'add' ? ' add' : line.type === 'remove' ? ' remove' : '') + (line.num === gotoLine ? ' goto-target' : '')} style="height: ${LINE_HEIGHT}px">
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
