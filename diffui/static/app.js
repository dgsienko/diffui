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
import { AgentStatusBar } from './components/AgentStatusBar.js';
import { AgentConfirmDialog } from './components/AgentConfirmDialog.js';
import { shortName } from './lib/utils.js';

const html = htm.bind(h);

async function safeFetch(url, opts) {
  try {
    const res = await fetch(url, opts);
    if (!res.ok) throw new Error(`${res.status}`);
    return res;
  } catch (err) {
    showToast(`Request failed: ${url.replace('/api/', '')}`, 'error');
    throw err;
  }
}

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
  const [sortByRisk, setSortByRisk] = useState(false);
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
  const scrollToLineRef = useRef(null);
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
    const res = await safeFetch('/api/theme/css');
    const data = await res.json();
    setThemeCss(data.css);
  }, []);

  const fetchRepos = useCallback(async () => {
    const res = await safeFetch('/api/repos');
    setRepos(await res.json());
  }, []);

  const fetchBranch = useCallback(async () => {
    const res = await safeFetch('/api/branch');
    setBranch(await res.json());
  }, []);

  const fetchCommits = useCallback(async () => {
    const res = await safeFetch('/api/commits');
    setCommits(await res.json());
  }, []);

  const fetchComments = useCallback(async () => {
    const res = await safeFetch('/api/comments');
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
    const res = await safeFetch(`/api/diff/${encodeURIComponent(path)}?view=${v}&context=${c}`);
    const data = await res.json();
    diffCache.current.set(cacheKey, data);
    if (activeFileRef.current === path) {
      setDiffData(data);
    }
  }, []);

  const fetchFiles = useCallback(async (v) => {
    const currentView = v || view;
    const res = await safeFetch(`/api/files?view=${currentView}`);
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

  // Restore scroll position after diff renders, or scroll to a specific line
  useEffect(() => {
    if (activeFile && diffRef.current) {
      const targetLine = scrollToLineRef.current;
      if (targetLine !== null) {
        scrollToLineRef.current = null;
        requestAnimationFrame(() => {
          if (!diffRef.current) return;
          const el = diffRef.current.querySelector(`[data-line-new="${targetLine}"]`);
          if (el) {
            el.scrollIntoView({ block: 'center' });
            el.style.outline = '2px solid var(--accent)';
            setTimeout(() => { el.style.outline = ''; }, 2000);
          }
        });
      } else {
        const saved = scrollPositions.current.get(activeFile) || 0;
        requestAnimationFrame(() => {
          if (diffRef.current) diffRef.current.scrollTop = saved;
        });
      }
    }
  }, [diffData, activeFile]);

  latestCallbacks.current = { fetchFiles, fetchCommits, fetchComments, fetchDiff, fetchRepos, activeFile, comments };

  useEffect(() => {
    Promise.all([fetchTheme(), fetchRepos(), fetchBranch(), fetchCommits(), fetchFiles(), fetchComments()]).then(async () => {
      const res = await fetch('/api/session');
      const session = await res.json();
      if (session.activeFile) setActiveFile(session.activeFile);
      if (session.diffMode) setDiffMode(session.diffMode);
      if (session.showFileTree !== undefined) setShowFileTree(session.showFileTree);
      if (session.showReviewed !== undefined) setShowReviewed(session.showReviewed);
      if (session.scrollPositions) {
        for (const [k, v] of Object.entries(session.scrollPositions)) {
          scrollPositions.current.set(k, v);
        }
      }
      if (session.activeFile) fetchDiff(session.activeFile);
    });
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

  // Real-time updates — WebSocket with SSE fallback
  useEffect(() => {
    let cleanup = () => {};

    const handleEvents = (events) => {
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
    };

    const connectSSE = () => {
      const es = new EventSource('/api/events');
      es.onmessage = (e) => {
        try { handleEvents(JSON.parse(e.data).events); } catch {}
      };
      cleanup = () => es.close();
    };

    const wsProto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProto}//${location.host}/api/ws`;
    try {
      const ws = new WebSocket(wsUrl);
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.events) handleEvents(msg.events);
        } catch {}
      };
      ws.onclose = connectSSE;
      cleanup = () => ws.close();
    } catch {
      connectSSE();
    }

    const repoInterval = setInterval(() => latestCallbacks.current.fetchRepos(), 30000);
    return () => { cleanup(); clearInterval(repoInterval); };
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

  const handleCommentSelect = useCallback((filePath, lineIndex) => {
    scrollToLineRef.current = lineIndex;
    handleFileSelect(filePath);
  }, [handleFileSelect]);

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
    showToast(`Comment added to ${shortName(filePath)}`, 'success');
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

  const pollTimers = useRef([]);
  const dismissTimer = useRef(null);
  useEffect(() => () => { pollTimers.current.forEach(clearInterval); clearTimeout(dismissTimer.current); }, []);

  const [taskStatus, setTaskStatus] = useState(null);

  const runAsyncTask = useCallback(async (runUrl, statusUrl, setRunning, { label, doneMsg, failMsg }) => {
    const r = await fetch(runUrl, { method: 'POST' });
    const data = await r.json();
    if (!data.ok) { showToast(data.error || 'Failed to start', 'error'); return data; }
    setRunning(true);
    const startTime = Date.now();
    setTaskStatus({ label, startTime, status: 'running' });
    const poll = setInterval(async () => {
      try {
        const s = await fetch(statusUrl);
        const status = await s.json();
        if (!status.running) {
          clearInterval(poll);
          pollTimers.current = pollTimers.current.filter(t => t !== poll);
          setRunning(false);
          const ok = status.exit_code === 0;
          const msg = ok ? (typeof doneMsg === 'function' ? doneMsg(data) : doneMsg) : failMsg;
          setTaskStatus({ label, startTime, status: ok ? 'done' : 'failed', message: msg, endTime: Date.now() });
          dismissTimer.current = setTimeout(() => setTaskStatus(s => s?.startTime === startTime ? null : s), 10000);
        }
      } catch {
        clearInterval(poll);
        setRunning(false);
        setTaskStatus({ label, startTime, status: 'failed', message: 'Lost connection', endTime: Date.now() });
      }
    }, 3000);
    pollTimers.current.push(poll);
    return data;
  }, []);

  const [agentRunning, setAgentRunning] = useState(false);
  const [showAgentConfirm, setShowAgentConfirm] = useState(null);

  const handleSendToAgent = useCallback(async () => {
    const r = await fetch('/api/agent/prompt', { method: 'POST' });
    const data = await r.json();
    if (!data.ok) { showToast(data.error || 'No comments to address', 'error'); return; }
    setShowAgentConfirm(data);
  }, []);

  const handleConfirmAgent = useCallback(() => {
    setShowAgentConfirm(null);
    runAsyncTask(
      '/api/agent/run', '/api/agent/status', setAgentRunning,
      { label: 'Addressing comments', doneMsg: 'Comments addressed', failMsg: 'Agent failed' },
    );
  }, [runAsyncTask]);

  const [explainRunning, setExplainRunning] = useState(false);
  const handleExplain = useCallback(() => runAsyncTask(
    '/api/explain', '/api/explain/status', setExplainRunning,
    { label: 'Generating explanation', doneMsg: (d) => `Explanation ready: ${d.output_path}`, failMsg: 'Explanation generation failed' },
  ), [runAsyncTask]);

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

  const commentNavRef = useRef(0);
  const navigateComment = useCallback((direction) => {
    const allComments = [];
    for (const [filePath, fileComments] of Object.entries(latestCallbacks.current.comments || {})) {
      for (const c of fileComments) {
        allComments.push({ filePath, lineNum: c.file_line_num || c.line_index });
      }
    }
    if (!allComments.length) return;
    if (direction === 'next') {
      commentNavRef.current = (commentNavRef.current + 1) % allComments.length;
    } else {
      commentNavRef.current = (commentNavRef.current - 1 + allComments.length) % allComments.length;
    }
    const target = allComments[commentNavRef.current];
    scrollToLineRef.current = target.lineNum;
    handleFileSelect(target.filePath);
    showToast(`Comment ${commentNavRef.current + 1}/${allComments.length}`);
  }, [handleFileSelect]);

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

  const visibleFiles = useMemo(() => {
    let filtered = showReviewed ? files : files.filter(f => !f.reviewed);
    if (sortByRisk) filtered = [...filtered].sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0));
    return filtered;
  }, [files, showReviewed, sortByRisk]);
  const activeFileReviewed = useMemo(() => files.find(f => f.path === activeFile)?.reviewed, [files, activeFile]);

  visibleFilesRef.current = visibleFiles;

  // Persist session state on changes (debounced)
  const saveTimerRef = useRef(null);
  useEffect(() => {
    clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      const scrollObj = {};
      scrollPositions.current.forEach((v, k) => { scrollObj[k] = v; });
      fetch('/api/session', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          activeFile,
          diffMode,
          showFileTree,
          showReviewed,
          scrollPositions: scrollObj,
        }),
      }).catch(() => {});
    }, 1000);
  }, [activeFile, diffMode, showFileTree, showReviewed]);

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
      } else if (e.key === 'S') {
        handleExportSummary();
      } else if (e.key === 'Y') {
        handleCopyGitLabLink();
      } else if (e.key === 'b') {
        setShowFileTree(v => !v);
      } else if (e.key === 'c') {
        document.dispatchEvent(new CustomEvent('diffui:comment-on-hovered'));
      } else if (e.key === 'n' || e.key === 'p') {
        navigateComment(e.key === 'n' ? 'next' : 'prev');
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

  const searchMatchCount = useMemo(() => {
    if (!searchTerm || !diffData?.hunks) return 0;
    const lower = searchTerm.toLowerCase();
    let count = 0;
    for (const hunk of diffData.hunks) {
      for (const line of hunk.lines) {
        if (line.text && line.text.toLowerCase().includes(lower)) count++;
      }
    }
    return count;
  }, [searchTerm, diffData]);

  const reviewedCount = useMemo(() => files.filter(f => f.reviewed).length, [files]);
  const commentStats = useMemo(() => {
    let total = 0, open = 0;
    for (const arr of Object.values(comments || {})) {
      total += arr.length;
      open += arr.filter(c => (c.status || 'open') !== 'resolved').length;
    }
    return { total, open };
  }, [comments]);
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
    { id: 'export-summary', label: 'Copy review summary', keys: 'S', category: 'Actions' },
    { id: 'sort-risk', label: 'Toggle sort by risk', category: 'Actions' },
    { id: 'send-to-agent', label: 'Send comments to agent', category: 'Agent' },
    { id: 'explain', label: 'Explain changes (generate HTML)', category: 'Agent' },
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
      case 'export-summary': handleExportSummary(); break;
      case 'sort-risk': setSortByRisk(v => { showToast(v ? 'Default file order' : 'Sorted by risk'); return !v; }); break;
      case 'send-to-agent': handleSendToAgent(); break;
      case 'explain': handleExplain(); break;
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
      onCommentSelect=${handleCommentSelect}
      agentRunning=${agentRunning}
      onSendToAgent=${handleSendToAgent}
    />
    ${taskStatus && html`
      <${AgentStatusBar}
        task=${taskStatus}
        onDismiss=${() => setTaskStatus(null)}
      />
    `}
    ${showSearch && html`
      <${SearchBar}
        value=${searchTerm}
        onChange=${setSearchTerm}
        onClose=${() => { setShowSearch(false); setSearchTerm(''); }}
        matchCount=${searchMatchCount}
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
                reviewed=${activeFileReviewed}
              />`
            : diffMode === 'file'
            ? html`<${FullFileViewer}
                containerRef=${diffRef}
                filePath=${activeFile}
                view=${view}
                onToggleReview=${handleToggleReview}
                reviewed=${activeFileReviewed}
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
                  reviewed=${activeFileReviewed}
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
                    reviewed=${activeFileReviewed}
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
      <div class="legend-fixed">
        <span class="risk-dot risk-medium"></span> medium risk
        <span class="risk-dot risk-high" style="margin-left: 8px"></span> high risk
      </div>
    </div>
    ${showCommandPalette && html`
      <${CommandPalette}
        commands=${paletteCommands}
        onExecute=${handleCommand}
        onClose=${() => setShowCommandPalette(false)}
      />
    `}
    ${showAgentConfirm && html`
      <${AgentConfirmDialog}
        agentCli=${showAgentConfirm.agent_cli}
        commentCount=${showAgentConfirm.comment_count}
        onConfirm=${handleConfirmAgent}
        onCancel=${() => setShowAgentConfirm(null)}
      />
    `}
    ${showCompletion && html`
      <${CompletionScreen}
        fileCount=${files.length}
        commentStats=${commentStats}
        onDismiss=${() => setShowCompletion(false)}
      />
    `}
    <${ToastContainer} />
  `;
}

render(html`<${App} />`, document.getElementById('app'));
