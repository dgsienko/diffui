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
import { CommentsPanel } from './components/CommentsPanel.js';
import { FileFilterBar } from './components/FileFilterBar.js';
import { GoToLineDialog } from './components/GoToLineDialog.js';
import { shortName, mod } from './lib/utils.js';

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
  const [searchMatchIndex, setSearchMatchIndex] = useState(0);
  const [showSearch, setShowSearch] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [showFileTree, setShowFileTree] = useState(true);
  const [showCommentsPanel, setShowCommentsPanel] = useState(false);
  const [showFileFilter, setShowFileFilter] = useState(false);
  const [fileFilter, setFileFilter] = useState('');
  const [diffMode, setDiffMode] = useState('unified');
  const [contextLines, setContextLines] = useState(3);
  const [showCompletion, setShowCompletion] = useState(false);
  const [showCommandPalette, setShowCommandPalette] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [showGoToLine, setShowGoToLine] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [ignoreWhitespace, setIgnoreWhitespace] = useState(false);
  const [showIgnored, setShowIgnored] = useState(false);
  const [collapseAll, setCollapseAll] = useState(null);
  const collapseVersion = useRef(0);
  const [fontSize, setFontSize] = useState(13);
  const [wordWrap, setWordWrap] = useState(false);
  const [keybindings, setKeybindings] = useState({});
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
  const ignoreWsRef = useRef(false);
  ignoreWsRef.current = ignoreWhitespace;

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

  const fetchDiff = useCallback(async (path, ctx, wsOverride) => {
    if (!path) return;
    const c = ctx ?? contextRef.current;
    const v = viewRef.current;
    const ws = wsOverride !== undefined ? wsOverride : ignoreWsRef.current;
    const cacheKey = `${path}:${v}:c${c}:ws${ws}`;
    const cached = diffCache.current.get(cacheKey);
    if (cached) {
      setDiffData(cached);
      return;
    }
    const res = await safeFetch(`/api/diff/${encodeURIComponent(path)}?view=${v}&context=${c}&ignore_whitespace=${ws}`);
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

  const flashLineRef = useRef(null);
  const scrollToLineAndFlash = useCallback((lineNum) => {
    if (!diffRef.current) return false;
    const el = diffRef.current.querySelector(`[data-line-new="${lineNum}"]`);
    if (!el) return false;
    el.scrollIntoView({ block: 'center' });
    el.style.outline = '2px solid var(--accent)';
    clearTimeout(flashLineRef.current);
    flashLineRef.current = setTimeout(() => { el.style.outline = ''; }, 2000);
    return true;
  }, []);

  useEffect(() => {
    if (!activeFile || !diffRef.current) return;
    const targetLine = scrollToLineRef.current;
    let rafId;
    if (targetLine !== null) {
      scrollToLineRef.current = null;
      rafId = requestAnimationFrame(() => scrollToLineAndFlash(targetLine));
    } else {
      const saved = scrollPositions.current.get(activeFile) || 0;
      rafId = requestAnimationFrame(() => {
        if (diffRef.current) diffRef.current.scrollTop = saved;
      });
    }
    return () => cancelAnimationFrame(rafId);
  }, [diffData, activeFile, scrollToLineAndFlash]);

  latestCallbacks.current = { fetchFiles, fetchCommits, fetchComments, fetchDiff, fetchRepos, activeFile, comments };

  useEffect(() => {
    Promise.all([fetchTheme(), fetchRepos(), fetchBranch(), fetchCommits(), fetchFiles(), fetchComments()]).then(async () => {
      try {
        const [sessionRes, settingsRes] = await Promise.all([fetch('/api/session'), fetch('/api/settings')]);
        const session = await sessionRes.json();
        const settings = await settingsRes.json();
        if (session.activeFile) setActiveFile(session.activeFile);
        if (session.diffMode) setDiffMode(session.diffMode);
        if (session.showFileTree !== undefined) setShowFileTree(session.showFileTree);
        if (session.showReviewed !== undefined) setShowReviewed(session.showReviewed);
        if (session.scrollPositions) {
          for (const [k, v] of Object.entries(session.scrollPositions)) {
            scrollPositions.current.set(k, v);
          }
        }
        if (settings.font_size) setFontSize(settings.font_size);
        if (settings.word_wrap !== undefined) setWordWrap(settings.word_wrap);
        if (settings.keybindings) setKeybindings(settings.keybindings);
        if (session.activeFile) fetchDiff(session.activeFile);
      } catch {}
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

  useEffect(() => {
    document.documentElement.style.setProperty('--code-font-size', `${fontSize}px`);
  }, [fontSize]);

  useEffect(() => {
    document.documentElement.classList.toggle('word-wrap-enabled', wordWrap);
  }, [wordWrap]);

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
      setWsConnected(false);
      const es = new EventSource('/api/events');
      es.onopen = () => setWsConnected(true);
      es.onerror = () => setWsConnected(false);
      es.onmessage = (e) => {
        try { handleEvents(JSON.parse(e.data).events); } catch {}
      };
      cleanup = () => { es.close(); setWsConnected(false); };
    };

    const wsProto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProto}//${location.host}/api/ws`;
    try {
      const ws = new WebSocket(wsUrl);
      ws.onopen = () => setWsConnected(true);
      ws.onclose = () => { setWsConnected(false); connectSSE(); };
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.events) handleEvents(msg.events);
        } catch {}
      };
      cleanup = () => { ws.close(); setWsConnected(false); };
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
    const cacheKey = `${path}:${viewRef.current}:c${contextRef.current}:ws${ignoreWsRef.current}`;
    const cached = diffCache.current.get(cacheKey);
    if (cached) {
      setDiffData(cached);
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

  const handleBulkResolve = useCallback(async (filePath) => {
    const r = await fetch('/api/comments/bulk-resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_path: filePath || null, action: 'resolve' }),
    });
    const data = await r.json();
    if (data.count > 0) {
      showToast(`Resolved ${data.count} comment${data.count === 1 ? '' : 's'}`, 'success');
      await Promise.all([fetchComments(), fetchFiles()]);
    } else {
      showToast('No open comments to resolve');
    }
  }, [fetchComments, fetchFiles]);

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
    if (settings.font_size !== undefined) setFontSize(settings.font_size);
    if (settings.word_wrap !== undefined) setWordWrap(settings.word_wrap);
    if (settings.keybindings !== undefined) setKeybindings(settings.keybindings);
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
    const hasOpen = Object.values(latestCallbacks.current.comments || {}).some(
      arr => arr.some(c => (c.status || 'open') !== 'resolved')
    );
    if (!hasOpen) { showToast('No open comments to send', 'error'); return; }
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

  const handleSortByRisk = useCallback(() => {
    setSortByRisk(v => { showToast(v ? 'Default file order' : 'Sorted by risk'); return !v; });
  }, []);

  const [explainRunning, setExplainRunning] = useState(false);
  const handleExplain = useCallback(() => runAsyncTask(
    '/api/explain', '/api/explain/status', setExplainRunning,
    { label: 'Generating explanation', doneMsg: () => ({ text: 'Explanation ready', url: `${location.origin}/api/explain/view` }), failMsg: 'Explanation generation failed' },
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

  const handleNextUnreviewed = useCallback(() => {
    const vf = visibleFilesRef.current;
    const next = vf.find(f => !f.reviewed);
    if (next) {
      handleFileSelect(next.path);
      showToast(`Jumped to ${next.short_name}`);
    } else {
      showToast('All files reviewed');
    }
  }, [handleFileSelect]);

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

  const handleToggleWhitespace = useCallback(() => {
    setIgnoreWhitespace(v => {
      const next = !v;
      showToast(next ? 'Hiding whitespace changes' : 'Showing whitespace changes');
      diffCache.current.clear();
      const af = activeFileRef.current;
      if (af) fetchDiff(af, undefined, next);
      return next;
    });
  }, [fetchDiff]);

  const handleCollapseAll = useCallback((action) => {
    collapseVersion.current += 1;
    setCollapseAll({ action, version: collapseVersion.current });
    showToast(action === 'collapse' ? 'All hunks collapsed' : 'All hunks expanded');
  }, []);

  const handleGoToLine = useCallback((lineNum) => {
    setShowGoToLine(false);
    if (!scrollToLineAndFlash(lineNum)) {
      showToast(`Line ${lineNum} not found in diff`);
    }
  }, [scrollToLineAndFlash]);

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

  const visibleFiles = useMemo(() => {
    let filtered = showReviewed ? files : files.filter(f => !f.reviewed);
    if (!showIgnored) {
      filtered = filtered.filter(f => !f.ignored);
    }
    if (fileFilter) {
      const lower = fileFilter.toLowerCase();
      filtered = filtered.filter(f => f.path.toLowerCase().includes(lower));
    }
    if (sortByRisk) filtered = [...filtered].sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0));
    return filtered;
  }, [files, showReviewed, sortByRisk, fileFilter, showIgnored]);
  const activeFileReviewed = useMemo(() => files.find(f => f.path === activeFile)?.reviewed, [files, activeFile]);

  visibleFilesRef.current = visibleFiles;

  const reviewedCount = useMemo(() => files.filter(f => f.reviewed).length, [files]);
  const commentStats = useMemo(() => {
    let total = 0, open = 0;
    for (const arr of Object.values(comments || {})) {
      total += arr.length;
      open += arr.filter(c => (c.status || 'open') !== 'resolved').length;
    }
    return { total, open };
  }, [comments]);

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

  showCompletionRef.current = showCompletion;
  dialogOpenRef.current = showSettings || showSearch || showFileFilter || showShortcuts || showCommandPalette || showGoToLine;
  const prevReviewedRef = useRef(null);
  useEffect(() => {
    if (prevReviewedRef.current !== null && files.length > 0
        && reviewedCount === files.length
        && prevReviewedRef.current < files.length) {
      setShowCompletion(true);
    }
    prevReviewedRef.current = reviewedCount;
  }, [reviewedCount, files.length]);

  useEffect(() => {
    const key = (id) => keybindings[id] || null;

    const handler = (e) => {
      if (showCompletionRef.current) { setShowCompletion(false); return; }
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;

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
        setSearchTerm('');
        return;
      }

      if (dialogOpenRef.current) return;

      if ((e.ctrlKey || e.metaKey) && e.key === 'g') {
        e.preventDefault();
        setShowGoToLine(v => !v);
        return;
      }

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
      } else if (e.key === (key('toggle-review') || 'r')) {
        handleToggleReview();
      } else if (e.key === (key('toggle-show-reviewed') || 'a')) {
        setShowReviewed(v => !v);
      } else if (e.key === (key('copy-path') || 'y')) {
        handleCopyPath();
      } else if (e.key === (key('sort-risk') || 's')) {
        handleSortByRisk();
      } else if (e.key === (key('export-summary') || 'S')) {
        handleExportSummary();
      } else if (e.key === 'Y') {
        handleCopyGitLabLink();
      } else if (e.key === (key('toggle-file-tree') || 'b')) {
        setShowFileTree(v => !v);
      } else if (e.key === (key('next-unreviewed') || ']')) {
        handleNextUnreviewed();
      } else if (e.key === (key('comment-line') || 'c')) {
        document.dispatchEvent(new CustomEvent('diffui:comment-on-hovered'));
      } else if (e.key === 'n' || e.key === 'p') {
        navigateComment(e.key === 'n' ? 'next' : 'prev');
      } else if (e.key === 'j' || e.key === 'k') {
        scrollToHunk(e.key === 'j' ? 'next' : 'prev');
      } else if (e.key === 'w') {
        handleToggleWhitespace();
      } else if (e.ctrlKey && !e.metaKey && e.shiftKey && (e.key === 'f' || e.key === 'F')) {
        e.preventDefault();
        setShowFileFilter(v => { if (v) setFileFilter(''); return !v; });
      } else if (e.ctrlKey && !e.metaKey && (e.key === 'f' || e.key === 'F')) {
        e.preventDefault();
        setShowSearch(v => !v);
      } else if (e.key === '?') {
        setShowShortcuts(v => !v);
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [keybindings]);

  const paletteCommands = useMemo(() => [
    { id: 'comment-line', label: 'Comment on hovered line', keys: keybindings['comment-line'] || 'c', category: 'Actions' },
    { id: 'toggle-review', label: 'Toggle reviewed', keys: keybindings['toggle-review'] || 'r', category: 'Actions' },
    { id: 'toggle-show-reviewed', label: 'Show/hide reviewed files', keys: keybindings['toggle-show-reviewed'] || 'a', category: 'Actions' },
    { id: 'prev-file', label: 'Previous file', keys: '←', category: 'Navigation' },
    { id: 'next-file', label: 'Next file', keys: '→', category: 'Navigation' },
    { id: 'prev-hunk', label: 'Previous hunk', keys: 'k', category: 'Navigation' },
    { id: 'next-hunk', label: 'Next hunk', keys: 'j', category: 'Navigation' },
    { id: 'go-to-line', label: 'Go to line', keys: `${mod}+G`, category: 'Navigation' },
    { id: 'copy-path', label: 'Copy file path', keys: keybindings['copy-path'] || 'y', category: 'Actions' },
    { id: 'copy-gitlab-link', label: 'Copy GitLab link', keys: 'Y', category: 'Actions' },
    { id: 'toggle-file-tree', label: 'Toggle file tree', keys: keybindings['toggle-file-tree'] || 'b', category: 'Actions' },
    { id: 'search', label: 'Search in diff', keys: 'Ctrl+F', category: 'Actions' },
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
    { id: 'export-summary', label: 'Copy review summary', keys: keybindings['export-summary'] || 'S', category: 'Actions' },
    { id: 'sort-risk', label: 'Toggle sort by risk', keys: keybindings['sort-risk'] || 's', category: 'Actions' },
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
      case 'toggle-word-wrap': { const nw = !wordWrap; setWordWrap(nw); handleSettingsChange({ word_wrap: nw }); break; }
      case 'font-size-up': { const ns = Math.min(fontSize + 1, 24); setFontSize(ns); handleSettingsChange({ font_size: ns }); break; }
      case 'font-size-down': { const ns = Math.max(fontSize - 1, 8); setFontSize(ns); handleSettingsChange({ font_size: ns }); break; }
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

  return html`
    <${TopBar}
      repos=${repos}
      branch=${branch}
      commits=${commits}
      view=${view}
      fileCount=${files.length}
      reviewedCount=${reviewedCount}
      showReviewed=${showReviewed}
      files=${files}
      comments=${comments}
      openCommentCount=${commentStats.open}
      onViewChange=${handleViewChange}
      onRepoSwitch=${handleRepoSwitch}
      diffMode=${diffMode}
      onDiffModeChange=${setDiffMode}
      showPreview=${showPreview}
      onTogglePreview=${() => setShowPreview(v => !v)}
      activeFile=${activeFile}
      onToggleReviewed=${() => setShowReviewed(v => !v)}
      onOpenSettings=${() => setShowSettings(v => !v)}
      onToggleCommentsPanel=${() => setShowCommentsPanel(v => !v)}
      showCommentsPanel=${showCommentsPanel}
      onToggleFileTree=${() => setShowFileTree(v => !v)}
      onToggleFileFilter=${() => setShowFileFilter(v => { if (v) setFileFilter(''); return !v; })}
      showFileTree=${showFileTree}
      showFileFilter=${showFileFilter}
      agentRunning=${agentRunning}
      onSendToAgent=${handleSendToAgent}
      explainRunning=${explainRunning}
      onExplain=${handleExplain}
      wsConnected=${wsConnected}
      ignoreWhitespace=${ignoreWhitespace}
      onToggleWhitespace=${handleToggleWhitespace}
      keybindings=${keybindings}
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
        onClose=${() => { setShowSearch(false); setSearchTerm(''); setSearchMatchIndex(0); }}
        matchCount=${searchMatchCount}
        matchIndex=${searchMatchIndex}
        onNext=${() => navigateSearchMatch('next')}
        onPrev=${() => navigateSearchMatch('prev')}
      />
    `}
    ${showFileFilter && html`
      <${FileFilterBar}
        value=${fileFilter}
        onChange=${setFileFilter}
        onClose=${() => { setShowFileFilter(false); setFileFilter(''); }}
        fileCount=${visibleFiles.length}
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
      ${showCommentsPanel && html`
        <${CommentsPanel}
          comments=${comments}
          onSelect=${handleCommentSelect}
          onClose=${() => setShowCommentsPanel(false)}
          onBulkResolve=${handleBulkResolve}
        />
      `}
      ${loading
        ? html`<div class="loading">Loading...</div>`
        : !activeFile
          ? files.length === 0
            ? html`<div class="empty-state"><span class="empty-state-title">No changed files</span><span class="empty-state-hint">This branch has no diff against the merge base</span></div>`
            : html`<div class="empty-state"><span class="empty-state-title">Select a file</span><span class="empty-state-hint">Choose a file from the tabs or explorer</span></div>`
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
                    collapseAll=${collapseAll}
                    onBulkResolve=${() => handleBulkResolve(activeFile)}
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
        fontSize=${fontSize}
        wordWrap=${wordWrap}
        keybindings=${keybindings}
      />
    `}
    ${showShortcuts && html`
      <${ShortcutOverlay} onClose=${() => setShowShortcuts(false)} keybindings=${keybindings} />
    `}
    ${showGoToLine && html`
      <${GoToLineDialog}
        onSubmit=${handleGoToLine}
        onClose=${() => setShowGoToLine(false)}
      />
    `}
    <div class="legend">
      <div class="legend-items">
        <span><kbd>${mod}+K</kbd> commands</span>
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
        <span class=${'connection-dot' + (wsConnected ? ' connected' : '')}></span>
        ${wsConnected ? 'Live' : 'Offline'}
        <span class="risk-dot risk-medium" style="margin-left: 8px"></span> medium risk
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
