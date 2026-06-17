import { useState, useRef, useCallback, useEffect } from 'preact/hooks';

export function shortName(path) {
  return path.split('/').pop();
}

export function mergeRef(containerRef) {
  return (el) => { if (containerRef) containerRef.current = el; };
}

export const isMac = navigator.platform.includes('Mac');
export const mod = isMac ? '⌘' : 'Ctrl';

export function useResize(initial, min, max) {
  const [width, setWidth] = useState(initial);
  const ref = useRef(null);
  const listeners = useRef(null);

  useEffect(() => () => {
    if (listeners.current) {
      document.removeEventListener('mousemove', listeners.current.onMove);
      document.removeEventListener('mouseup', listeners.current.onUp);
    }
  }, []);

  const onResizeStart = useCallback((e) => {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = ref.current?.offsetWidth || initial;
    const onMove = (e) => {
      const w = Math.max(min, Math.min(max, startWidth + e.clientX - startX));
      if (ref.current) ref.current.style.width = w + 'px';
    };
    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      listeners.current = null;
      if (ref.current) setWidth(ref.current.offsetWidth);
    };
    listeners.current = { onMove, onUp };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, [initial, min, max]);

  return { ref, width, onResizeStart };
}
