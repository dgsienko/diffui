import { useCallback } from 'preact/hooks';
import { showToast } from '../components/Toast.js';
import { shortName } from './utils.js';
import { sendJson, commentUrl } from './api.js';

export function useComments({ fetchComments, fetchFiles, fetchDiff, diffCache, activeFileRef }) {
  const handleAddComment = useCallback(async (filePath, lineIndex, lineText, fileLineNum, commentText, category, suggestion, selection) => {
    await sendJson('/api/comments', 'POST', {
      file_path: filePath,
      line_index: lineIndex,
      line_text: lineText,
      file_line_num: fileLineNum,
      comment: commentText,
      category: category || '',
      suggestion: suggestion || '',
      selected_text: selection?.selectedText || '',
      sel_start: selection?.selStart ?? null,
      sel_end: selection?.selEnd ?? null,
      sel_end_index: selection?.endLineIndex ?? null,
    });
    showToast(`Comment added to ${shortName(filePath)}`, 'success');
    await Promise.all([fetchComments(), fetchFiles()]);
  }, [fetchComments, fetchFiles]);

  const handleDeleteComment = useCallback(async (filePath, commentId) => {
    await fetch(commentUrl(filePath, commentId), { method: 'DELETE' });
    await Promise.all([fetchComments(), fetchFiles()]);
  }, [fetchComments, fetchFiles]);

  const handleEditComment = useCallback(async (filePath, commentId, newText) => {
    await sendJson(commentUrl(filePath, commentId), 'PUT', { comment: newText });
    await fetchComments();
  }, [fetchComments]);

  const handleReplyComment = useCallback(async (filePath, commentId, text) => {
    await sendJson(commentUrl(filePath, commentId, '/reply'), 'POST', { text });
    await fetchComments();
  }, [fetchComments]);

  const handleResolveComment = useCallback(async (filePath, commentId) => {
    await fetch(commentUrl(filePath, commentId, '/resolve'), { method: 'POST' });
    await fetchComments();
  }, [fetchComments]);

  const handleBulkResolve = useCallback(async (filePath) => {
    const r = await sendJson('/api/comments/bulk-resolve', 'POST', { file_path: filePath || null, action: 'resolve' });
    const data = await r.json();
    if (data.count > 0) {
      showToast(`Resolved ${data.count} comment${data.count === 1 ? '' : 's'}`, 'success');
      await Promise.all([fetchComments(), fetchFiles()]);
    } else {
      showToast('No open comments to resolve');
    }
  }, [fetchComments, fetchFiles]);

  const handleApplySuggestion = useCallback(async (filePath, commentId) => {
    const r = await fetch(commentUrl(filePath, commentId, '/apply'), { method: 'POST' });
    const data = await r.json();
    if (data.ok) {
      showToast('Suggestion applied', 'success');
      diffCache.current.clear();
      await Promise.all([fetchComments(), fetchFiles()]);
      if (activeFileRef.current) fetchDiff(activeFileRef.current);
    } else {
      showToast(data.error || 'Failed to apply', 'error');
    }
  }, [fetchComments, fetchFiles, fetchDiff]);

  const commentActions = {
    onAddComment: handleAddComment,
    onDeleteComment: handleDeleteComment,
    onEditComment: handleEditComment,
    onReplyComment: handleReplyComment,
    onResolveComment: handleResolveComment,
    onApplySuggestion: handleApplySuggestion,
  };

  return { commentActions, handleBulkResolve };
}
