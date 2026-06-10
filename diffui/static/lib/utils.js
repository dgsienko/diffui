export function shortName(path) {
  return path.split('/').pop();
}

export function mergeRef(containerRef) {
  return (el) => { if (containerRef) containerRef.current = el; };
}

export const isMac = navigator.platform.includes('Mac');
export const mod = isMac ? '⌘' : 'Ctrl';
