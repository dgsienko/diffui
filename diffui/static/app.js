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
import { DiffStatsBar } from './components/DiffStatsBar.js';
import { FileTree } from './components/FileTree.js';
import { SplitDiffViewer } from './components/SplitDiffViewer.js';
import { FullFileViewer } from './components/FullFileViewer.js';
import { Minimap } from './components/Minimap.js';

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
  const diffRef = useRef(null);
  const diffCache = useRef(new Map());
  const scrollPositions = useRef(new Map());
  const latestCallbacks = useRef({});

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

  const contextRef = useRef(contextLines);
  contextRef.current = contextLines;
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

  const viewRef = useRef(view);
  viewRef.current = view;

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

  const activeFileRef = useRef(activeFile);
  activeFileRef.current = activeFile;
  const handleFileSelect = useCallback((path) => {
    if (activeFileRef.current && diffRef.current) {
      scrollPositions.current.set(activeFileRef.current, diffRef.current.scrollTop);
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
  }, [activeFile, fetchFiles]);

  const handleAddComment = useCallback(async (filePath, lineIndex, lineText, fileLineNum, commentText) => {
    await fetch('/api/comments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        file_path: filePath,
        line_index: lineIndex,
        line_text: lineText,
        file_line_num: fileLineNum,
        comment: commentText,
      }),
    });
    showToast('Comment added', 'success');
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

  const handleExpandContext = useCallback(() => {
    const levels = [3, 10, 50, 9999];
    const next = levels.find(l => l > contextLines) || 9999;
    setContextLines(next);
    const af = activeFileRef.current;
    if (af) {
      for (const key of [...diffCache.current.keys()]) {
        if (key.startsWith(`${af}:`)) diffCache.current.delete(key);
      }
      fetchDiff(af, next);
    }
    showToast(next >= 9999 ? 'Showing full context' : `Expanded to ${next} lines of context`);
  }, [contextLines, fetchDiff]);

  const branchRef = useRef(branch);
  branchRef.current = branch;
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
    const url = `${base}/-/blob/${ref}/${af}`;
    navigator.clipboard.writeText(url);
    showToast('GitLab link copied');
  }, []);

  const visibleFiles = useMemo(() => showReviewed ? files : files.filter(f => !f.reviewed), [files, showReviewed]);

  const visibleFilesRef = useRef(visibleFiles);
  visibleFilesRef.current = visibleFiles;

  // Keyboard shortcuts — stable effect, reads current values via refs
  useEffect(() => {
    const handler = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;

      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        const vf = visibleFilesRef.current;
        const af = activeFileRef.current;
        const idx = vf.findIndex(f => f.path === af);
        if (idx === -1) return;
        const next = e.key === 'ArrowLeft'
          ? (idx - 1 + vf.length) % vf.length
          : (idx + 1) % vf.length;
        setActiveFile(vf[next].path);
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
      } else if (e.key === 'j' || e.key === 'k') {
        const container = diffRef.current;
        if (!container) return;
        const headers = [...container.querySelectorAll('.hunk-header')];
        if (!headers.length) return;
        const scrollTop = container.scrollTop;
        if (e.key === 'j') {
          const next = headers.find(h => h.offsetTop > scrollTop + 10);
          if (next) container.scrollTo({ top: next.offsetTop, behavior: 'instant' });
        } else {
          const prev = [...headers].reverse().find(h => h.offsetTop < scrollTop - 10);
          if (prev) container.scrollTo({ top: prev.offsetTop, behavior: 'instant' });
        }
      } else if (e.ctrlKey && e.key === 'f') {
        e.preventDefault();
        setShowSearch(v => !v);
      } else if (e.key === '?') {
        setShowShortcuts(v => !v);
      } else if (e.key === 'Escape') {
        setShowSettings(false);
        setShowSearch(false);
        setShowShortcuts(false);
        setSearchTerm('');
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  const reviewedCount = files.filter(f => f.reviewed).length;

  return html`
    <${TopBar}
      repos=${repos}
      branch=${branch}
      commits=${commits}
      view=${view}
      fileCount=${files.length}
      reviewedCount=${reviewedCount}
      showReviewed=${showReviewed}
      onViewChange=${handleViewChange}
      onRepoSwitch=${handleRepoSwitch}
      diffMode=${diffMode}
      onDiffModeChange=${setDiffMode}
      onToggleReviewed=${() => setShowReviewed(v => !v)}
      onOpenSettings=${() => setShowSettings(v => !v)}
    />
    ${showSearch && html`
      <${SearchBar}
        value=${searchTerm}
        onChange=${setSearchTerm}
        onClose=${() => { setShowSearch(false); setSearchTerm(''); }}
      />
    `}
    <${DiffStatsBar} files=${visibleFiles} />
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
          : diffMode === 'file'
            ? html`<${FullFileViewer}
                ref=${diffRef}
                filePath=${activeFile}
                view=${view}
                onToggleReview=${handleToggleReview}
                reviewed=${files.find(f => f.path === activeFile)?.reviewed}
              />`
            : diffMode === 'split' && diffData
              ? html`<${SplitDiffViewer}
                  ref=${diffRef}
                  data=${diffData}
                  comments=${comments}
                  onToggleReview=${handleToggleReview}
                  onAddComment=${handleAddComment}
                  onDeleteComment=${handleDeleteComment}
                  onEditComment=${handleEditComment}
                  onReplyComment=${handleReplyComment}
                  reviewed=${files.find(f => f.path === activeFile)?.reviewed}
                />`
              : diffData
                ? html`<${DiffViewer}
                    ref=${diffRef}
                    data=${diffData}
                    comments=${comments}
                    searchTerm=${searchTerm}
                    onToggleReview=${handleToggleReview}
                    onAddComment=${handleAddComment}
                    onDeleteComment=${handleDeleteComment}
                    onEditComment=${handleEditComment}
                    onReplyComment=${handleReplyComment}
                    onOpenInEditor=${handleOpenInEditor}
                    onExpandContext=${handleExpandContext}
                    contextLines=${contextLines}
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
      <span><kbd>←</kbd><kbd>→</kbd> prev/next file</span>
      <span><kbd>j</kbd><kbd>k</kbd> next/prev hunk</span>
      <span><kbd>r</kbd> toggle reviewed</span>
      <span><kbd>a</kbd> show/hide reviewed</span>
      <span><kbd>y</kbd> copy path</span>
      <span><kbd>Ctrl+F</kbd> search</span>
      <span><kbd>Ctrl+Click</kbd> open in editor</span>
      <span><kbd>Right-Click</kbd> add comment</span>
      <span><kbd>?</kbd> shortcuts</span>
    </div>
    <${ToastContainer} />
  `;
}

render(html`<${App} />`, document.getElementById('app'));
