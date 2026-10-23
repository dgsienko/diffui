import { useCallback } from 'preact/hooks';
import { showToast } from '../components/Toast.js';

export function useCopyActions({ activeFileRef, branchRef, hoveredLineRef }) {
  const handleCopyPath = useCallback(() => {
    const af = activeFileRef.current;
    if (af) {
      navigator.clipboard.writeText(af);
      showToast(`Copied: ${af}`);
    }
  }, []);

  const handleExportSummary = useCallback(async () => {
    const res = await fetch('/api/review-summary');
    const data = await res.json();
    await navigator.clipboard.writeText(data.markdown);
    showToast('Review summary copied to clipboard', 'success');
  }, []);

  const handleCopyGitLabLink = useCallback(() => {
    const af = activeFileRef.current;
    const b = branchRef.current;
    if (!af || !b?.remote_url) return;
    const remote = b.remote_url;
    let base;
    if (remote.startsWith('git@')) {
      const hostPath = remote.split(':')[1].replace(/\.git$/, '');
      const host = remote.split('@')[1].split(':')[0];
      base = `https://${host}/${hostPath}`;
    } else {
      base = remote.replace(/\.git$/, '');
    }
    const ref = b.head_sha ? b.head_sha.slice(0, 12) : b.name;
    const lineNum = hoveredLineRef.current;
    const url = `${base}/-/blob/${ref}/${af}${lineNum ? '#L' + lineNum : ''}`;
    navigator.clipboard.writeText(url);
    showToast(lineNum ? `GitLab link copied (line ${lineNum})` : 'GitLab link copied');
  }, []);

  return { handleCopyPath, handleExportSummary, handleCopyGitLabLink };
}
