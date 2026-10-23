import { useEffect, useMemo, useCallback } from 'preact/hooks';
import { mod, clampFont } from './utils.js';
import { kb } from './keys.js';

// Global keydown handler plus the command palette's command list and dispatcher.
export function useKeyboard({
  keybindings, fontSize, wordWrap,
  showCompletionRef, dialogOpenRef, visibleFilesRef, activeFileRef,
  handleFileSelect, handleToggleReview, handleCopyPath, handleSortByRisk, handleExportSummary,
  handleCopyGitLabLink, handleNextUnreviewed, navigateComment, scrollToHunk, handleToggleWhitespace,
  handleExpandContext, handleCollapseAll, handleSettingsChange, handleBulkResolve, handleSendToAgent, handleExplain,
  setDiffMode, setFileFilter, setSearchTerm, setShowCommandPalette, setShowCompletion, setShowFileFilter,
  setShowFileTree, setShowGoToLine, setShowRepoSearch, setShowReviewed, setShowSearch, setShowSettings, setShowShortcuts
}) {
  useEffect(() => {
    const handler = (e) => {
      if (showCompletionRef.current) { setShowCompletion(false); return; }
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
      if (e.target instanceof Element && e.target.closest('.agent-terminal-panel')) return;

      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setShowCommandPalette(v => !v);
        return;
      }
      if (e.key === 'Escape') {
        setShowSettings(false);
        setShowSearch(false);
        setShowShortcuts(false);
        setShowCommandPalette(false);
        setShowGoToLine(false);
        setShowRepoSearch(false);
        setSearchTerm('');
        return;
      }

      if (dialogOpenRef.current) return;

      if ((e.ctrlKey || e.metaKey) && e.key === 'g') {
        e.preventDefault();
        setShowGoToLine(v => !v);
        return;
      }

      if (e.ctrlKey && !e.metaKey && e.shiftKey && (e.key === 'f' || e.key === 'F')) {
        e.preventDefault();
        setShowFileFilter(v => { if (v) setFileFilter(''); return !v; });
        return;
      }
      if (e.ctrlKey && !e.metaKey && (e.key === 'f' || e.key === 'F')) {
        e.preventDefault();
        setShowSearch(v => !v);
        return;
      }

      // Don't hijack browser/OS shortcuts (copy, select-all, save, etc.)
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        const vf = visibleFilesRef.current;
        const af = activeFileRef.current;
        const idx = vf.findIndex(f => f.path === af);
        if (idx === -1) return;
        const next = e.key === 'ArrowLeft'
          ? (idx - 1 + vf.length) % vf.length
          : (idx + 1) % vf.length;
        handleFileSelect(vf[next].path);
        e.preventDefault();
      } else if (e.key === kb(keybindings, 'toggle-review')) {
        handleToggleReview();
      } else if (e.key === kb(keybindings, 'toggle-show-reviewed')) {
        setShowReviewed(v => !v);
      } else if (e.key === kb(keybindings, 'copy-path')) {
        handleCopyPath();
      } else if (e.key === kb(keybindings, 'sort-risk')) {
        handleSortByRisk();
      } else if (e.key === kb(keybindings, 'export-summary')) {
        handleExportSummary();
      } else if (e.key === 'Y') {
        handleCopyGitLabLink();
      } else if (e.key === kb(keybindings, 'toggle-file-tree')) {
        setShowFileTree(v => !v);
      } else if (e.key === kb(keybindings, 'next-unreviewed')) {
        handleNextUnreviewed();
      } else if (e.key === kb(keybindings, 'comment-line')) {
        document.dispatchEvent(new CustomEvent('diffui:comment-on-hovered'));
      } else if (e.key === 'n' || e.key === 'p') {
        navigateComment(e.key === 'n' ? 'next' : 'prev');
      } else if (e.key === 'j' || e.key === 'k') {
        scrollToHunk(e.key === 'j' ? 'next' : 'prev');
      } else if (e.key === 'w') {
        handleToggleWhitespace();
      } else if (e.key === '/') {
        e.preventDefault();
        setShowRepoSearch(true);
      } else if (e.key === '?') {
        setShowShortcuts(v => !v);
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [keybindings]);

  const paletteCommands = useMemo(() => [
    { id: 'comment-line', label: 'Comment on hovered line', keys: kb(keybindings, 'comment-line'), category: 'Actions' },
    { id: 'toggle-review', label: 'Toggle reviewed', keys: kb(keybindings, 'toggle-review'), category: 'Actions' },
    { id: 'toggle-show-reviewed', label: 'Show/hide reviewed files', keys: kb(keybindings, 'toggle-show-reviewed'), category: 'Actions' },
    { id: 'prev-file', label: 'Previous file', keys: '←', category: 'Navigation' },
    { id: 'next-file', label: 'Next file', keys: '→', category: 'Navigation' },
    { id: 'prev-hunk', label: 'Previous hunk', keys: 'k', category: 'Navigation' },
    { id: 'next-hunk', label: 'Next hunk', keys: 'j', category: 'Navigation' },
    { id: 'go-to-line', label: 'Go to line', keys: `${mod}+G`, category: 'Navigation' },
    { id: 'copy-path', label: 'Copy file path', keys: kb(keybindings, 'copy-path'), category: 'Actions' },
    { id: 'copy-gitlab-link', label: 'Copy GitLab link', keys: 'Y', category: 'Actions' },
    { id: 'toggle-file-tree', label: 'Toggle file tree', keys: kb(keybindings, 'toggle-file-tree'), category: 'Actions' },
    { id: 'search', label: 'Search in diff', keys: 'Ctrl+F', category: 'Actions' },
    { id: 'repo-search', label: 'Search files and text', keys: '/', category: 'Navigation' },
    { id: 'shortcuts', label: 'Show keyboard shortcuts', keys: '?', category: 'Help' },
    { id: 'settings', label: 'Open settings', category: 'Settings' },
    { id: 'mode-unified', label: 'Switch to unified diff', category: 'Settings' },
    { id: 'mode-split', label: 'Switch to split diff', category: 'Settings' },
    { id: 'mode-file', label: 'Switch to full file view', category: 'Settings' },
    { id: 'expand-context', label: 'Expand diff context', category: 'Actions' },
    { id: 'collapse-context', label: 'Collapse diff context', category: 'Actions' },
    { id: 'expand-all-hunks', label: 'Expand all hunks', category: 'Actions' },
    { id: 'collapse-all-hunks', label: 'Collapse all hunks', category: 'Actions' },
    { id: 'toggle-whitespace', label: 'Toggle ignore whitespace', keys: 'w', category: 'Actions' },
    { id: 'toggle-word-wrap', label: 'Toggle word wrap', category: 'Settings' },
    { id: 'font-size-up', label: 'Increase font size', category: 'Settings' },
    { id: 'font-size-down', label: 'Decrease font size', category: 'Settings' },
    { id: 'export-summary', label: 'Copy review summary', keys: kb(keybindings, 'export-summary'), category: 'Actions' },
    { id: 'sort-risk', label: 'Toggle sort by risk', keys: kb(keybindings, 'sort-risk'), category: 'Actions' },
    { id: 'bulk-resolve', label: 'Resolve all comments in file', category: 'Actions' },
    { id: 'bulk-resolve-all', label: 'Resolve all open comments', category: 'Actions' },
    { id: 'send-to-agent', label: 'Send comments to agent', category: 'Agent' },
    { id: 'explain', label: 'Explain changes (generate HTML)', category: 'Agent' },
  ], [keybindings]);

  const handleCommand = useCallback((id) => {
    const vf = visibleFilesRef.current;
    const af = activeFileRef.current;
    const idx = vf.findIndex(f => f.path === af);
    switch (id) {
      case 'comment-line': document.dispatchEvent(new CustomEvent('diffui:comment-on-hovered')); break;
      case 'toggle-review': handleToggleReview(); break;
      case 'toggle-show-reviewed': setShowReviewed(v => !v); break;
      case 'prev-file': if (vf.length) handleFileSelect(vf[(idx - 1 + vf.length) % vf.length].path); break;
      case 'next-file': if (vf.length) handleFileSelect(vf[(idx + 1) % vf.length].path); break;
      case 'copy-path': handleCopyPath(); break;
      case 'copy-gitlab-link': handleCopyGitLabLink(); break;
      case 'toggle-file-tree': setShowFileTree(v => !v); break;
      case 'search': setShowSearch(v => !v); break;
      case 'repo-search': setShowRepoSearch(true); break;
      case 'shortcuts': setShowShortcuts(v => !v); break;
      case 'settings': setShowSettings(v => !v); break;
      case 'mode-unified': setDiffMode('unified'); break;
      case 'mode-split': setDiffMode('split'); break;
      case 'mode-file': setDiffMode('file'); break;
      case 'expand-context': handleExpandContext('expand'); break;
      case 'collapse-context': handleExpandContext('collapse'); break;
      case 'expand-all-hunks': handleCollapseAll('expand'); break;
      case 'collapse-all-hunks': handleCollapseAll('collapse'); break;
      case 'toggle-whitespace': handleToggleWhitespace(); break;
      case 'toggle-word-wrap': handleSettingsChange({ word_wrap: !wordWrap }); break;
      case 'font-size-up': handleSettingsChange({ font_size: clampFont(fontSize + 1) }); break;
      case 'font-size-down': handleSettingsChange({ font_size: clampFont(fontSize - 1) }); break;
      case 'go-to-line': setShowGoToLine(v => !v); break;
      case 'export-summary': handleExportSummary(); break;
      case 'sort-risk': handleSortByRisk(); break;
      case 'bulk-resolve': handleBulkResolve(af); break;
      case 'bulk-resolve-all': handleBulkResolve(null); break;
      case 'send-to-agent': handleSendToAgent(); break;
      case 'explain': handleExplain(); break;
      case 'prev-hunk': scrollToHunk('prev'); break;
      case 'next-hunk': scrollToHunk('next'); break;
    }
  }, [handleToggleReview, handleFileSelect, handleCopyPath, handleCopyGitLabLink, handleExpandContext, handleCollapseAll, handleToggleWhitespace, handleExportSummary, handleSortByRisk, handleBulkResolve, handleSendToAgent, handleExplain, scrollToHunk, handleSettingsChange, wordWrap, fontSize]);

  return { paletteCommands, handleCommand };
}
