import { h, render } from 'preact';
import { useState, useEffect, useCallback, useRef } from 'preact/hooks';
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

  const fetchFiles = useCallback(async (v) => {
    const currentView = v || view;
    const res = await fetch(`/api/files?view=${currentView}`);
    const data = await res.json();
    setFiles(data);
    if (data.length > 0 && (!activeFile || !data.find(f => f.path === activeFile))) {
      const firstUnreviewed = data.find(f => !f.reviewed);
      setActiveFile((firstUnreviewed || data[0]).path);
    }
    setLoading(false);
  }, [view, activeFile]);

  const fetchDiff = useCallback(async (path, ctx) => {
    if (!path) return;
    const c = ctx ?? contextLines;
    const cacheKey = `${path}:${view}:c${c}`;
    const cached = diffCache.current.get(cacheKey);
    if (cached) {
      setDiffData(cached);
    }
    const res = await fetch(`/api/diff/${encodeURIComponent(path)}?view=${view}&context=${c}`);
    const data = await res.json();
    diffCache.current.set(cacheKey, data);
    setDiffData(data);
  }, [view, contextLines]);

  // Restore scroll position after diff renders
  useEffect(() => {
    if (activeFile && diffRef.current) {
      const saved = scrollPositions.current.get(activeFile) || 0;
      requestAnimationFrame(() => {
        if (diffRef.current) diffRef.current.scrollTop = saved;
      });
    }
  }, [diffData, activeFile]);

  useEffect(() => {
    Promise.all([fetchTheme(), fetchRepos(), fetchBranch(), fetchCommits(), fetchFiles(), fetchComments()]);
  }, []);

  useEffect(() => {
    if (activeFile) fetchDiff(activeFile);
  }, [activeFile, view]);

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

  // SSE real-time updates
  useEffect(() => {
    const es = new EventSource('/api/events');
    es.onmessage = (e) => {
      try {
        const { events } = JSON.parse(e.data);
        if (events.includes('git_changed') || events.includes('files_changed')) {
          diffCache.current.clear();
          fetchFiles();
          fetchCommits();
          fetchRepos();
          if (activeFile) fetchDiff(activeFile);
        }
        if (events.includes('comments_changed')) {
          fetchComments();
        }
      } catch {}
    };
    // Refresh sibling repo states periodically (they aren't covered by SSE)
    const repoInterval = setInterval(fetchRepos, 30000);
    return () => { es.close(); clearInterval(repoInterval); };
  }, [fetchFiles, fetchCommits, fetchComments, fetchDiff, fetchRepos, activeFile]);

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
    // Save scroll position of current file
    if (activeFile && diffRef.current) {
      scrollPositions.current.set(activeFile, diffRef.current.scrollTop);
    }
    setActiveFile(path);
  }, [activeFile]);

  const handleToggleReview = useCallback(async () => {
    if (!activeFile) return;
    const r = await fetch(`/api/reviewed/${encodeURIComponent(activeFile)}`, { method: 'POST' });
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
    if (activeFile) {
      navigator.clipboard.writeText(activeFile);
      showToast(`Copied: ${activeFile}`);
    }
  }, [activeFile]);

  const handleExpandContext = useCallback(() => {
    const levels = [3, 10, 50, 9999];
    const next = levels.find(l => l > contextLines) || 9999;
    setContextLines(next);
    for (const key of [...diffCache.current.keys()]) {
      if (key.startsWith(`${activeFile}:`)) diffCache.current.delete(key);
    }
    if (activeFile) fetchDiff(activeFile, next);
    showToast(next >= 9999 ? 'Showing full context' : `Expanded to ${next} lines of context`);
  }, [contextLines, activeFile, fetchDiff]);

  const handleCopyGitLabLink = useCallback(() => {
    if (!activeFile || !branch?.remote_url) return;
    const remote = branch.remote_url;
    let base;
    if (remote.startsWith('git@')) {
      const hostPath = remote.split(':')[1].replace(/\.git$/, '');
      const host = remote.split('@')[1].split(':')[0];
      base = `https://${host}/${hostPath}`;
    } else {
      base = remote.replace(/\.git$/, '');
    }
    const ref = branch.head_sha ? branch.head_sha.slice(0, 12) : branch.name;
    const url = `${base}/-/blob/${ref}/${activeFile}`;
    navigator.clipboard.writeText(url);
    showToast('GitLab link copied');
  }, [activeFile, branch]);

  const visibleFiles = showReviewed ? files : files.filter(f => !f.reviewed);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;

      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        const idx = visibleFiles.findIndex(f => f.path === activeFile);
        if (idx === -1) return;
        const next = e.key === 'ArrowLeft'
          ? (idx - 1 + visibleFiles.length) % visibleFiles.length
          : (idx + 1) % visibleFiles.length;
        setActiveFile(visibleFiles[next].path);
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
  }, [visibleFiles, activeFile, handleToggleReview, handleCopyPath]);

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
