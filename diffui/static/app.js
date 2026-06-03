import { h, render } from 'preact';
import { useState, useEffect, useCallback, useRef, useMemo } from 'preact/hooks';
import htm from 'htm';
import { TopBar } from './components/TopBar.js';
import { FileTabs } from './components/FileTabs.js';
import { DiffViewer } from './components/DiffViewer.js';
import { SettingsPanel } from './components/SettingsPanel.js';
import { SearchBar } from './components/SearchBar.js';
import { ToastContainer, showToast } from './components/Toast.js';
import { ShortcutOverlay } from './components/ShortcutOverlay.js';

import { FileTree } from './components/FileTree.js';
import { SplitDiffViewer } from './components/SplitDiffViewer.js';
import { FullFileViewer } from './components/FullFileViewer.js';
import { Minimap } from './components/Minimap.js';
import { CompletionScreen } from './components/CompletionScreen.js';
import { CommandPalette } from './components/CommandPalette.js';
import { PreviewViewer, isPreviewable } from './components/PreviewViewer.js';

const html = htm.bind(h);

function App() {
  const [repos, setRepos] = useState([]);
  const [files, setFiles] = useState([]);
  const [activeFile, setActiveFile] = useState(null);
  const [diffData, setDiffData] = useState(null);
  const [view, setView] = useState('all');
  const [commits, setCommits] = useState([]);
  const [branch, setBranch] = useState(null);
  const [comments, setComments] = useState({});
  const [loading, setLoading] = useState(true);
  const [themeCss, setThemeCss] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  const [showReviewed, setShowReviewed] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [showSearch, setShowSearch] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [showFileTree, setShowFileTree] = useState(false);
  const [diffMode, setDiffMode] = useState('unified');
  const [contextLines, setContextLines] = useState(3);
  const [showCompletion, setShowCompletion] = useState(false);
  const [showCommandPalette, setShowCommandPalette] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const diffRef = useRef(null);
  const diffCache = useRef(new Map());
  const scrollPositions = useRef(new Map());
  const hoveredLineRef = useRef(null);
  const latestCallbacks = useRef({});
  const activeFileRef = useRef(activeFile);
  activeFileRef.current = activeFile;
  const viewRef = useRef(view);
  viewRef.current = view;
  const contextRef = useRef(contextLines);
  contextRef.current = contextLines;
  const branchRef = useRef(branch);
  branchRef.current = branch;
  const visibleFilesRef = useRef([]);
  const showCompletionRef = useRef(false);
  const dialogOpenRef = useRef(false);

  const fetchTheme = useCallback(async () => {
    const res = await fetch('/api/theme/css');
    const data = await res.json();
    setThemeCss(data.css);
  }, []);

  const fetchRepos = useCallback(async () => {
    const res = await fetch('/api/repos');
    setRepos(await res.json());
  }, []);

  const fetchBranch = useCallback(async () => {
    const res = await fetch('/api/branch');
    setBranch(await res.json());
  }, []);

  const fetchCommits = useCallback(async () => {
    const res = await fetch('/api/commits');
    setCommits(await res.json());
  }, []);

  const fetchComments = useCallback(async () => {
    const res = await fetch('/api/comments');
    setComments(await res.json());
  }, []);

  const fetchDiff = useCallback(async (path, ctx) => {
    if (!path) return;
    const c = ctx ?? contextRef.current;
    const v = viewRef.current;
    const cacheKey = `${path}:${v}:c${c}`;
    const cached = diffCache.current.get(cacheKey);
    if (cached) {
      setDiffData(cached);
      return;
    }
    const res = await fetch(`/api/diff/${encodeURIComponent(path)}?view=${v}&context=${c}`);
    const data = await res.json();
    diffCache.current.set(cacheKey, data);
    if (activeFileRef.current === path) {
      setDiffData(data);
    }
  }, []);

  const fetchFiles = useCallback(async (v) => {
    const currentView = v || view;
    const res = await fetch(`/api/files?view=${currentView}`);
    const data = await res.json();
    setFiles(data);
    const current = activeFileRef.current;
    if (data.length > 0 && (!current || !data.find(f => f.path === current))) {
      const firstUnreviewed = data.find(f => !f.reviewed);
      const newActive = (firstUnreviewed || data[0]).path;
      setActiveFile(newActive);
      fetchDiff(newActive);
    }
    setLoading(false);
  }, [view, fetchDiff]);

  // Restore scroll position after diff renders
  useEffect(() => {
    if (activeFile && diffRef.current) {
      const saved = scrollPositions.current.get(activeFile) || 0;
      requestAnimationFrame(() => {
        if (diffRef.current) diffRef.current.scrollTop = saved;
      });
    }
  }, [diffData, activeFile]);

  latestCallbacks.current = { fetchFiles, fetchCommits, fetchComments, fetchDiff, fetchRepos, activeFile };

  useEffect(() => {
    Promise.all([fetchTheme(), fetchRepos(), fetchBranch(), fetchCommits(), fetchFiles(), fetchComments()]);
  }, []);

  useEffect(() => {
    if (themeCss) {
      let style = document.getElementById('theme-vars');
      if (!style) {
        style = document.createElement('style');
        style.id = 'theme-vars';
        document.head.appendChild(style);
      }
      style.textContent = themeCss;
    }
  }, [themeCss]);

  // SSE real-time updates — use ref to avoid reconnecting on every callback change
  useEffect(() => {
    const es = new EventSource('/api/events');
    es.onmessage = (e) => {
      try {
        const { events } = JSON.parse(e.data);
        const cb = latestCallbacks.current;
        if (events.includes('git_changed') || events.includes('files_changed')) {
          diffCache.current.clear();
          cb.fetchFiles();
          cb.fetchCommits();
          cb.fetchRepos();
          if (cb.activeFile) cb.fetchDiff(cb.activeFile);
        }
        if (events.includes('comments_changed')) {
          cb.fetchComments();
        }
      } catch {}
    };
    const repoInterval = setInterval(() => latestCallbacks.current.fetchRepos(), 30000);
    return () => { es.close(); clearInterval(repoInterval); };
  }, []);

  const handleViewChange = useCallback(async (newView) => {
    setView(newView);
    setActiveFile(null);
    setDiffData(null);
    diffCache.current.clear();
    scrollPositions.current.clear();
    await fetchFiles(newView);
  }, [fetchFiles]);

  const handleRepoSwitch = useCallback(async (index) => {
    setLoading(true);
    await fetch('/api/repo/switch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ index }),
    });
    setActiveFile(null);
    setDiffData(null);
    setView('all');
    diffCache.current.clear();
    scrollPositions.current.clear();
    await Promise.all([fetchRepos(), fetchBranch(), fetchCommits(), fetchFiles('all'), fetchComments()]);
    setLoading(false);
  }, [fetchRepos, fetchBranch, fetchCommits, fetchFiles, fetchComments]);

  const handleFileSelect = useCallback((path) => {
    if (activeFileRef.current && diffRef.current) {
      scrollPositions.current.set(activeFileRef.current, diffRef.current.scrollTop);
    }
    const cacheKey = `${path}:${viewRef.current}:c${contextRef.current}`;
    if (!diffCache.current.has(cacheKey)) {
      setDiffData(null);
    }
    setActiveFile(path);
    fetchDiff(path);
  }, [fetchDiff]);

  const handleToggleReview = useCallback(async () => {
    const af = activeFileRef.current;
    if (!af) return;
    const r = await fetch(`/api/reviewed/${encodeURIComponent(af)}`, { method: 'POST' });
    const data = await r.json();
    showToast(data.reviewed ? 'Marked as reviewed' : 'Marked as unreviewed', 'success');
    await fetchFiles();
    if (data.reviewed) {
      const vf = visibleFilesRef.current;
      const next = vf.find(f => !f.reviewed);
      if (next) handleFileSelect(next.path);
    }
  }, [fetchFiles, handleFileSelect]);

  const handleAddComment = useCallback(async (filePath, lineIndex, lineText, fileLineNum, commentText, category) => {
    await fetch('/api/comments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        file_path: filePath,
        line_index: lineIndex,
        line_text: lineText,
        file_line_num: fileLineNum,
        comment: commentText,
        category: category || '',
      }),
    });
    const shortName = filePath.split('/').pop();
    showToast(`Comment added to ${shortName}`, 'success');
    await Promise.all([fetchComments(), fetchFiles()]);
  }, [fetchComments, fetchFiles]);

  const handleDeleteComment = useCallback(async (filePath, commentId) => {
    await fetch(`/api/comments/${encodeURIComponent(filePath)}/${commentId}`, { method: 'DELETE' });
    await Promise.all([fetchComments(), fetchFiles()]);
  }, [fetchComments, fetchFiles]);

  const handleEditComment = useCallback(async (filePath, commentId, newText) => {
    await fetch(`/api/comments/${encodeURIComponent(filePath)}/${commentId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ comment: newText }),
    });
    await fetchComments();
  }, [fetchComments]);

  const handleReplyComment = useCallback(async (filePath, commentId, text) => {
    await fetch(`/api/comments/${encodeURIComponent(filePath)}/${commentId}/reply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    await fetchComments();
  }, [fetchComments]);

  const handleResolveComment = useCallback(async (filePath, commentId) => {
    await fetch(`/api/comments/${encodeURIComponent(filePath)}/${commentId}/resolve`, {
      method: 'POST',
    });
    await fetchComments();
  }, [fetchComments]);

  const handleApplySuggestion = useCallback(async (filePath, commentId) => {
    const r = await fetch(`/api/comments/${encodeURIComponent(filePath)}/${commentId}/apply`, {
      method: 'POST',
    });
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

  const handleOpenInEditor = useCallback(async (filePath, lineNum) => {
    await fetch('/api/editor/open', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_path: filePath, line_num: lineNum }),
    });
  }, []);

  const handleSettingsChange = useCallback(async (settings) => {
    const res = await fetch('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
    });
    const data = await res.json();
    if (data.css) setThemeCss(data.css);
  }, []);

  const handleCopyPath = useCallback(() => {
    const af = activeFileRef.current;
    if (af) {
      navigator.clipboard.writeText(af);
      showToast(`Copied: ${af}`);
    }
  }, []);

  const handleExpandContext = useCallback((direction = 'expand') => {
    const levels = [3, 10, 50, 9999];
    let next;
    if (direction === 'collapse') {
      next = [...levels].reverse().find(l => l < contextLines) || 3;
    } else {
      next = levels.find(l => l > contextLines) || 9999;
    }
    setContextLines(next);
    const af = activeFileRef.current;
    if (af) {
      for (const key of [...diffCache.current.keys()]) {
        if (key.startsWith(`${af}:`)) diffCache.current.delete(key);
      }
      fetchDiff(af, next);
    }
    const label = next >= 9999 ? 'Showing full context' : next <= 3 ? 'Default context (3 lines)' : `${direction === 'collapse' ? 'Collapsed' : 'Expanded'} to ${next} lines of context`;
    showToast(label);
  }, [contextLines, fetchDiff]);

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

  const visibleFiles = useMemo(() => showReviewed ? files : files.filter(f => !f.reviewed), [files, showReviewed]);

  visibleFilesRef.current = visibleFiles;

  // Keyboard shortcuts — stable effect, reads current values via refs
  useEffect(() => {
    const handler = (e) => {
      if (showCompletionRef.current) { setShowCompletion(false); return; }
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;

      // Global shortcuts — work even when dialogs are open
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
        setSearchTerm('');
        return;
      }

      // Context-aware: skip action shortcuts when a dialog is open
      if (dialogOpenRef.current) return;

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
      } else if (e.key === 'r') {
        handleToggleReview();
      } else if (e.key === 'a') {
        setShowReviewed(v => !v);
      } else if (e.key === 'y') {
        handleCopyPath();
      } else if (e.key === 'Y') {
        handleCopyGitLabLink();
      } else if (e.key === 'b') {
        setShowFileTree(v => !v);
      } else if (e.key === 'c') {
        document.dispatchEvent(new CustomEvent('diffui:comment-on-hovered'));
      } else if (e.key === 'j' || e.key === 'k') {
        scrollToHunk(e.key === 'j' ? 'next' : 'prev');
      } else if (e.ctrlKey && e.key === 'f') {
        e.preventDefault();
        setShowSearch(v => !v);
      } else if (e.key === '?') {
        setShowShortcuts(v => !v);
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  const reviewedCount = useMemo(() => files.filter(f => f.reviewed).length, [files]);
  showCompletionRef.current = showCompletion;
  dialogOpenRef.current = showSettings || showSearch || showShortcuts || showCommandPalette;
  const prevReviewedRef = useRef(null);
  useEffect(() => {
    if (prevReviewedRef.current !== null && files.length > 0
        && reviewedCount === files.length
        && prevReviewedRef.current < files.length) {
      setShowCompletion(true);
    }
    prevReviewedRef.current = reviewedCount;
  }, [reviewedCount, files.length]);

  const paletteCommands = useMemo(() => [
    { id: 'comment-line', label: 'Comment on hovered line', keys: 'c', category: 'Actions' },
    { id: 'toggle-review', label: 'Toggle reviewed', keys: 'r', category: 'Actions' },
    { id: 'toggle-show-reviewed', label: 'Show/hide reviewed files', keys: 'a', category: 'Actions' },
    { id: 'prev-file', label: 'Previous file', keys: '←', category: 'Navigation' },
    { id: 'next-file', label: 'Next file', keys: '→', category: 'Navigation' },
    { id: 'prev-hunk', label: 'Previous hunk', keys: 'k', category: 'Navigation' },
    { id: 'next-hunk', label: 'Next hunk', keys: 'j', category: 'Navigation' },
    { id: 'copy-path', label: 'Copy file path', keys: 'y', category: 'Actions' },
    { id: 'copy-gitlab-link', label: 'Copy GitLab link', keys: 'Y', category: 'Actions' },
    { id: 'toggle-file-tree', label: 'Toggle file tree', keys: 'b', category: 'Actions' },
    { id: 'search', label: 'Search in diff', keys: 'Ctrl+F', category: 'Actions' },
    { id: 'shortcuts', label: 'Show keyboard shortcuts', keys: '?', category: 'Help' },
    { id: 'settings', label: 'Open settings', category: 'Settings' },
    { id: 'mode-unified', label: 'Switch to unified diff', category: 'Settings' },
    { id: 'mode-split', label: 'Switch to split diff', category: 'Settings' },
    { id: 'mode-file', label: 'Switch to full file view', category: 'Settings' },
    { id: 'expand-context', label: 'Expand diff context', category: 'Actions' },
    { id: 'collapse-context', label: 'Collapse diff context', category: 'Actions' },
  ], []);

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
      case 'shortcuts': setShowShortcuts(v => !v); break;
      case 'settings': setShowSettings(v => !v); break;
      case 'mode-unified': setDiffMode('unified'); break;
      case 'mode-split': setDiffMode('split'); break;
      case 'mode-file': setDiffMode('file'); break;
      case 'expand-context': handleExpandContext('expand'); break;
      case 'collapse-context': handleExpandContext('collapse'); break;
      case 'prev-hunk': scrollToHunk('prev'); break;
      case 'next-hunk': scrollToHunk('next'); break;
    }
  }, [handleToggleReview, handleFileSelect, handleCopyPath, handleCopyGitLabLink, handleExpandContext]);

  return html`
    <${TopBar}
      repos=${repos}
      branch=${branch}
      commits=${commits}
      view=${view}
      fileCount=${files.length}
      reviewedCount=${reviewedCount}
      showReviewed=${showReviewed}
      comments=${comments}
      onViewChange=${handleViewChange}
      onRepoSwitch=${handleRepoSwitch}
      diffMode=${diffMode}
      onDiffModeChange=${setDiffMode}
      showPreview=${showPreview}
      onTogglePreview=${() => setShowPreview(v => !v)}
      activeFile=${activeFile}
      onToggleReviewed=${() => setShowReviewed(v => !v)}
      onOpenSettings=${() => setShowSettings(v => !v)}
      onCommentSelect=${handleFileSelect}
    />
    ${showSearch && html`
      <${SearchBar}
        value=${searchTerm}
        onChange=${setSearchTerm}
        onClose=${() => { setShowSearch(false); setSearchTerm(''); }}
      />
    `}
    <${FileTabs}
      files=${visibleFiles}
      activeFile=${activeFile}
      onSelect=${handleFileSelect}
    />
    <div class="main-content">
      ${showFileTree && html`
        <${FileTree}
          files=${visibleFiles}
          activeFile=${activeFile}
          onSelect=${handleFileSelect}
          onClose=${() => setShowFileTree(false)}
        />
      `}
      ${loading
        ? html`<div class="loading">Loading...</div>`
        : !activeFile
          ? files.length === 0
            ? html`<div class="empty-state">No changed files</div>`
            : html`<div class="loading">Select a file</div>`
          : showPreview && isPreviewable(activeFile)
            ? html`<${PreviewViewer}
                containerRef=${diffRef}
                filePath=${activeFile}
                onToggleReview=${handleToggleReview}
                reviewed=${files.find(f => f.path === activeFile)?.reviewed}
              />`
            : diffMode === 'file'
            ? html`<${FullFileViewer}
                containerRef=${diffRef}
                filePath=${activeFile}
                view=${view}
                onToggleReview=${handleToggleReview}
                reviewed=${files.find(f => f.path === activeFile)?.reviewed}
              />`
            : diffMode === 'split' && diffData
              ? html`<${SplitDiffViewer}
                  containerRef=${diffRef}
                  data=${diffData}
                  comments=${comments}
                  onToggleReview=${handleToggleReview}
                  onAddComment=${handleAddComment}
                  onDeleteComment=${handleDeleteComment}
                  onEditComment=${handleEditComment}
                  onReplyComment=${handleReplyComment}
                  onResolveComment=${handleResolveComment}
                  onApplySuggestion=${handleApplySuggestion}
                  reviewed=${files.find(f => f.path === activeFile)?.reviewed}
                />`
              : diffData
                ? html`<${DiffViewer}
                    containerRef=${diffRef}
                    data=${diffData}
                    comments=${comments}
                    searchTerm=${searchTerm}
                    onToggleReview=${handleToggleReview}
                    onAddComment=${handleAddComment}
                    onDeleteComment=${handleDeleteComment}
                    onEditComment=${handleEditComment}
                    onReplyComment=${handleReplyComment}
                    onResolveComment=${handleResolveComment}
                    onApplySuggestion=${handleApplySuggestion}
                    onOpenInEditor=${handleOpenInEditor}
                    onExpandContext=${handleExpandContext}
                    contextLines=${contextLines}
                    onLineHover=${(num) => { hoveredLineRef.current = num; }}
                    reviewed=${files.find(f => f.path === activeFile)?.reviewed}
                  />`
                : html`<div class="loading">Loading...</div>`
      }
      ${diffMode === 'unified' && diffData && html`
        <${Minimap} diffData=${diffData} comments=${comments} containerRef=${diffRef} />
      `}
    </div>
    ${showSettings && html`
      <${SettingsPanel}
        onChange=${handleSettingsChange}
        onClose=${() => setShowSettings(false)}
      />
    `}
    ${showShortcuts && html`
      <${ShortcutOverlay} onClose=${() => setShowShortcuts(false)} />
    `}
    <div class="legend">
      <div class="legend-items">
        <span><kbd>Ctrl+K</kbd> commands</span>
        <span><kbd>?</kbd> shortcuts</span>
        <span><kbd>←</kbd><kbd>→</kbd> prev/next file</span>
        <span><kbd>j</kbd><kbd>k</kbd> next/prev hunk</span>
        <span><kbd>r</kbd> toggle reviewed</span>
        <span><kbd>a</kbd> show/hide reviewed</span>
        <span><kbd>c</kbd> comment</span>
        <span><kbd>Ctrl+F</kbd> search</span>
        <span><kbd>y</kbd> copy path</span>
      </div>
    </div>
    ${showCommandPalette && html`
      <${CommandPalette}
        commands=${paletteCommands}
        onExecute=${handleCommand}
        onClose=${() => setShowCommandPalette(false)}
      />
    `}
    ${showCompletion && html`
      <${CompletionScreen}
        fileCount=${files.length}
        comments=${comments}
        onDismiss=${() => setShowCompletion(false)}
      />
    `}
    <${ToastContainer} />
  `;
}

render(html`<${App} />`, document.getElementById('app'));
