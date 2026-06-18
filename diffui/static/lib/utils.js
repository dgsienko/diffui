import { useState, useRef, useCallback, useEffect } from 'preact/hooks';

export function shortName(path) {
  return path.split('/').pop();
}

export function mergeRef(containerRef) {
  return (el) => { if (containerRef) containerRef.current = el; };
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
