import { useEffect, useRef } from 'preact/hooks';
import { sendJson } from './api.js';

// Debounced save of the view state that survives a reload.
export function useSessionSave({ activeFile, diffMode, showFileTree, showReviewed, scrollPositions, browsingRef }) {
  const saveTimerRef = useRef(null);
  useEffect(() => {
    clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      const scrollObj = {};
      scrollPositions.current.forEach((v, k) => { scrollObj[k] = v; });
      sendJson('/api/session', 'PUT', {
        activeFile: browsingRef.current ? undefined : activeFile,
        diffMode,
        showFileTree,
        showReviewed,
        scrollPositions: scrollObj,
      }).catch(() => {});
    }, 1000);
  }, [activeFile, diffMode, showFileTree, showReviewed]);
}
