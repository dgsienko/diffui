import { useEffect, useCallback, useRef } from 'preact/hooks';
import { nearestNewLine } from './utils.js';

// Scroll position save and restore per file, jump-to-line with a flash, and hunk stepping.
export function useDiffScroll({ diffRef, activeFile, activeFileRef, diffData, scrollPositions, scrollToLineRef, searchJumpRef }) {
  const saveScrollPosition = useCallback(() => {
    if (activeFileRef.current && diffRef.current) {
      scrollPositions.current.set(activeFileRef.current, diffRef.current.scrollTop);
    }
  }, []);

  const flashLineRef = useRef(null);
  const scrollToLineAndFlash = useCallback((lineNum) => {
    if (!diffRef.current) return false;
    const el = diffRef.current.querySelector(`[data-line-new="${lineNum}"]`);
    if (!el) return false;
    el.scrollIntoView({ block: 'center' });
    el.style.outline = '2px solid var(--accent)';
    clearTimeout(flashLineRef.current);
    flashLineRef.current = setTimeout(() => { el.style.outline = ''; }, 2000);
    return true;
  }, []);

  useEffect(() => {
    if (!activeFile || !diffRef.current) return;
    let targetLine = scrollToLineRef.current;
    const jump = searchJumpRef.current;
    if (jump && diffData?.file_path === jump.path) {
      searchJumpRef.current = null;
      targetLine = nearestNewLine(diffData, jump.line);
    }
    let rafId;
    if (targetLine !== null) {
      scrollToLineRef.current = null;
      rafId = requestAnimationFrame(() => scrollToLineAndFlash(targetLine));
    } else {
      const saved = scrollPositions.current.get(activeFile) || 0;
      rafId = requestAnimationFrame(() => {
        if (diffRef.current) diffRef.current.scrollTop = saved;
      });
    }
    return () => cancelAnimationFrame(rafId);
  }, [diffData, activeFile, scrollToLineAndFlash]);

  const scrollToHunk = useCallback((direction) => {
    const container = diffRef.current;
    if (!container) return;
    const headers = [...container.querySelectorAll('.hunk-header')];
    if (!headers.length) return;
    const scrollTop = container.scrollTop;
    if (direction === 'next') {
      const next = headers.find(h => h.offsetTop > scrollTop + 10);
      if (next) container.scrollTo({ top: next.offsetTop, behavior: 'instant' });
    } else {
      const prev = [...headers].reverse().find(h => h.offsetTop < scrollTop - 10);
      if (prev) container.scrollTo({ top: prev.offsetTop, behavior: 'instant' });
    }
  }, []);

  return { saveScrollPosition, scrollToLineAndFlash, scrollToHunk };
}
