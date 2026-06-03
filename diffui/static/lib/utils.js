export function shortName(path) {
  return path.split('/').pop();
}

export function mergeRef(containerRef) {
  return (el) => { if (containerRef) containerRef.current = el; };
}
