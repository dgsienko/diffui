import { useMemo, useEffect, useCallback } from 'preact/hooks';

// Matches of the in-diff search term, and stepping through them.
export function useDiffSearch({ searchTerm, searchMatchIndex, setSearchMatchIndex, diffData, diffRef }) {
  const searchMatches = useMemo(() => {
    if (!searchTerm || !diffData?.hunks) return [];
    const lower = searchTerm.toLowerCase();
    const matches = [];
    for (const hunk of diffData.hunks) {
      for (const line of hunk.lines) {
        if (line.text && line.text.toLowerCase().includes(lower)) {
          matches.push(line.new_num || line.old_num || line.index);
        }
      }
    }
    return matches;
  }, [searchTerm, diffData]);

  const searchMatchCount = searchMatches.length;

  useEffect(() => {
    setSearchMatchIndex(0);
  }, [searchTerm]);

  const navigateSearchMatch = useCallback((direction) => {
    if (!searchMatches.length) return;
    const nextIdx = direction === 'next'
      ? (searchMatchIndex + 1) % searchMatches.length
      : (searchMatchIndex - 1 + searchMatches.length) % searchMatches.length;
    setSearchMatchIndex(nextIdx);
    const lineNum = searchMatches[nextIdx];
    if (diffRef.current && lineNum) {
      const el = diffRef.current.querySelector(`[data-line-new="${lineNum}"]`);
      if (el) el.scrollIntoView({ block: 'center' });
    }
  }, [searchMatches, searchMatchIndex]);

  return { searchMatchCount, navigateSearchMatch };
}
