import { useState, useRef, useCallback, useEffect } from 'preact/hooks';

export function shortName(path) {
  return path.split('/').pop();
}

export function mergeRef(...refs) {
  return (el) => { for (const r of refs) { if (r) r.current = el; } };
}

// Wrap the plain-text character ranges [start, end) in <mark>, walking the
// syntax-highlighted HTML so tags/entities are preserved and offsets stay aligned
// with the rendered text content of the line.
export function highlightRanges(htmlStr, ranges) {
  if (!ranges || !ranges.length || !htmlStr) return htmlStr;
  const inRange = (idx) => ranges.some(r => idx >= r.start && idx < r.end);
  let result = '';
  let i = 0;
  let charIdx = 0;
  let buf = '';
  let bufInRange = false;
  const flush = () => {
    if (!buf) return;
    result += bufInRange ? `<mark class="comment-range">${buf}</mark>` : buf;
    buf = '';
  };
  const pushChar = (ch) => {
    const r = inRange(charIdx);
    if (buf && r !== bufInRange) flush();
    bufInRange = r;
    buf += ch;
    charIdx++;
  };
  while (i < htmlStr.length) {
    if (htmlStr[i] === '<') {
      flush();
      const end = htmlStr.indexOf('>', i);
      if (end === -1) { result += htmlStr.slice(i); break; }
      result += htmlStr.slice(i, end + 1);
      i = end + 1;
    } else if (htmlStr[i] === '&') {
      const semi = htmlStr.indexOf(';', i);
      if (semi === -1) { pushChar(htmlStr[i]); i++; }
      else { pushChar(htmlStr.slice(i, semi + 1)); i = semi + 1; }
    } else {
      pushChar(htmlStr[i]);
      i++;
    }
  }
  flush();
  return result;
}

// Character offset of a (node, offset) point within an element's text content.
export function offsetInElement(el, node, nodeOffset) {
  const range = document.createRange();
  range.selectNodeContents(el);
  range.setEnd(node, nodeOffset);
  return range.toString().length;
}

// Build the [{start, end}] ranges for a line from its range-scoped comments.
export function commentRangesFor(lineComments) {
  return lineComments
    .filter(c => c.sel_start != null && c.sel_end != null && c.sel_end > c.sel_start)
    .map(c => ({ start: c.sel_start, end: c.sel_end }));
}

// Detect a text selection contained within a single code element (matched by
// codeSelector, e.g. '.diff-code' / '.split-code') whose line carries a
// data-line-index, and expose a floating-button anchor + pending-selection state.
export function useRangeSelection(codeSelector, containerRef) {
  const [selMenu, setSelMenu] = useState(null);
  const [pendingSelection, setPendingSelection] = useState(null);

  useEffect(() => {
    const codeElOf = (node) => {
      const el = node && node.nodeType === 3 ? node.parentElement : node;
      return el && el.closest ? el.closest(codeSelector) : null;
    };
    const onMouseUp = () => {
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed || !sel.rangeCount) { setSelMenu(null); return; }
      const text = sel.toString();
      if (!text.trim()) { setSelMenu(null); return; }
      const range = sel.getRangeAt(0);
      const startCode = codeElOf(range.startContainer);
      const endCode = codeElOf(range.endContainer);
      if (!startCode || startCode !== endCode) { setSelMenu(null); return; }
      const lineEl = startCode.closest('[data-line-index]');
      if (!lineEl) { setSelMenu(null); return; }
      const selStart = offsetInElement(startCode, range.startContainer, range.startOffset);
      const selEnd = offsetInElement(startCode, range.endContainer, range.endOffset);
      if (selEnd <= selStart) { setSelMenu(null); return; }
      const rect = range.getBoundingClientRect();
      setSelMenu({
        x: rect.left + rect.width / 2,
        y: rect.top,
        lineIndex: parseInt(lineEl.dataset.lineIndex),
        selStart,
        selEnd,
        selectedText: text,
      });
    };
    document.addEventListener('mouseup', onMouseUp);
    return () => document.removeEventListener('mouseup', onMouseUp);
  }, [codeSelector]);

  useEffect(() => {
    const el = containerRef?.current;
    if (!el) return;
    const onScroll = () => setSelMenu(null);
    el.addEventListener('scroll', onScroll, true);
    return () => el.removeEventListener('scroll', onScroll, true);
  }, [containerRef]);

  // Capture the current selection into pendingSelection and open its line's box.
  const commentFromSelection = (openLine) => {
    if (!selMenu) return;
    setPendingSelection({
      lineIndex: selMenu.lineIndex,
      selStart: selMenu.selStart,
      selEnd: selMenu.selEnd,
      selectedText: selMenu.selectedText,
    });
    openLine(selMenu.lineIndex);
    setSelMenu(null);
    window.getSelection()?.removeAllRanges();
  };

  return { selMenu, setSelMenu, pendingSelection, setPendingSelection, commentFromSelection };
}

export const isMac = navigator.platform.includes('Mac');
export const mod = isMac ? '⌘' : 'Ctrl';

export function useResize(initial, min, max, axis = 'x') {
  const [size, setSize] = useState(initial);
  const ref = useRef(null);
  const listeners = useRef(null);
  const isY = axis === 'y';
  const prop = isY ? 'height' : 'width';
  const offsetProp = isY ? 'offsetHeight' : 'offsetWidth';

  useEffect(() => () => {
    if (listeners.current) {
      document.removeEventListener('mousemove', listeners.current.onMove);
      document.removeEventListener('mouseup', listeners.current.onUp);
    }
  }, []);

  const onResizeStart = useCallback((e) => {
    e.preventDefault();
    const startPos = isY ? e.clientY : e.clientX;
    const startSize = ref.current?.[offsetProp] || initial;
    const resolvedMax = typeof max === 'function' ? max() : max;
    const onMove = (e) => {
      const pos = isY ? e.clientY : e.clientX;
      const delta = isY ? startPos - pos : pos - startPos;
      const s = Math.max(min, Math.min(resolvedMax, startSize + delta));
      if (ref.current) ref.current.style[prop] = s + 'px';
    };
    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      listeners.current = null;
      if (ref.current) setSize(ref.current[offsetProp]);
    };
    listeners.current = { onMove, onUp };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, [initial, min, max, isY, prop, offsetProp]);

  return { ref, size, onResizeStart };
}
