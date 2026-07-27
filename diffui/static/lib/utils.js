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

export const NO_COMMENTS = { comments: [], ranges: [] };

// Index a file's comments by diff line in one pass: which comments anchor to a
// line, and which [{start, end}] spans it highlights. A range comment may cover
// several lines — it runs from sel_start on line_index to sel_end on
// sel_end_index — so interior lines highlight whole and the edges partially.
export function commentsByLine(fileComments) {
  const byLine = new Map();
  const at = (i) => {
    let entry = byLine.get(i);
    if (!entry) { entry = { comments: [], ranges: [] }; byLine.set(i, entry); }
    return entry;
  };
  for (const c of fileComments) {
    at(c.line_index).comments.push(c);
    if (c.sel_start == null || c.sel_end == null) continue;
    const last = c.sel_end_index ?? c.line_index;
    if (last === c.line_index) {
      if (c.sel_end > c.sel_start) at(c.line_index).ranges.push({ start: c.sel_start, end: c.sel_end });
      continue;
    }
    at(c.line_index).ranges.push({ start: c.sel_start, end: Infinity });
    for (let i = c.line_index + 1; i < last; i++) at(i).ranges.push({ start: 0, end: Infinity });
    if (c.sel_end > 0) at(last).ranges.push({ start: 0, end: c.sel_end });
  }
  return byLine;
}

// Detect a text selection inside the code column (matched by codeSelector, e.g.
// '.diff-code' / '.split-code') of one or more lines carrying a data-line-index,
// and expose a floating-button anchor + pending-selection state. groupSelector,
// when given, confines a selection to one column (split view's two panes
// interleave line indices, so a cross-pane drag is not a range).
export function useRangeSelection(codeSelector, containerRef, groupSelector) {
  const [selMenu, setSelMenu] = useState(null);
  const [pendingSelection, setPendingSelection] = useState(null);

  useEffect(() => {
    const elOf = (node) => (node && node.nodeType === 3 ? node.parentElement : node);
    const closestOf = (node, selector) => {
      const el = elOf(node);
      return el && el.closest ? el.closest(selector) : null;
    };
    // The code element the point falls in, or that line's code column when the
    // point landed elsewhere on the row (gutter, blame cell, line padding).
    const codeFor = (node, lineEl) => closestOf(node, codeSelector) || lineEl.querySelector(codeSelector);
    const onMouseUp = () => {
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed || !sel.rangeCount) { setSelMenu(null); return; }
      const text = sel.toString();
      if (!text.trim()) { setSelMenu(null); return; }
      const range = sel.getRangeAt(0);
      const startLine = closestOf(range.startContainer, '[data-line-index]');
      const endLine = closestOf(range.endContainer, '[data-line-index]');
      if (!startLine || !endLine) { setSelMenu(null); return; }
      if (groupSelector && closestOf(startLine, groupSelector) !== closestOf(endLine, groupSelector)) {
        setSelMenu(null);
        return;
      }
      const startCode = codeFor(range.startContainer, startLine);
      const endCode = codeFor(range.endContainer, endLine);
      if (!startCode || !endCode) { setSelMenu(null); return; }
      const lineIndex = parseInt(startLine.dataset.lineIndex);
      const endLineIndex = parseInt(endLine.dataset.lineIndex);
      if (isNaN(lineIndex) || isNaN(endLineIndex) || endLineIndex < lineIndex) { setSelMenu(null); return; }
      const selStart = startCode.contains(range.startContainer)
        ? offsetInElement(startCode, range.startContainer, range.startOffset) : 0;
      const selEnd = endCode.contains(range.endContainer)
        ? offsetInElement(endCode, range.endContainer, range.endOffset) : endCode.textContent.length;
      if (endLineIndex === lineIndex && selEnd <= selStart) { setSelMenu(null); return; }
      // Anchor to the end of the selection — that's where the cursor just was.
      const rects = range.getClientRects();
      const rect = rects.length ? rects[rects.length - 1] : range.getBoundingClientRect();
      setSelMenu({
        x: rect.left + rect.width / 2,
        y: rect.top,
        lineIndex,
        endLineIndex,
        selStart,
        selEnd,
        selectedText: text,
      });
    };
    document.addEventListener('mouseup', onMouseUp);
    return () => document.removeEventListener('mouseup', onMouseUp);
  }, [codeSelector, groupSelector]);

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
      endLineIndex: selMenu.endLineIndex,
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
