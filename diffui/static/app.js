import { h, render } from 'preact';
import { useState, useEffect, useCallback, useRef, useMemo } from 'preact/hooks';
import htm from 'htm';
import { TopBar } from './components/TopBar.js';
import { FileHeader } from './components/FileHeader.js';
import { DiffViewer } from './components/DiffViewer.js';
import { SettingsPanel } from './components/SettingsPanel.js';
import { SearchBar } from './components/SearchBar.js';
import { ToastContainer, showToast } from './components/Toast.js';
import { ShortcutOverlay } from './components/ShortcutOverlay.js';

import { FileTree, treeOrder } from './components/FileTree.js';
import { SplitDiffViewer } from './components/SplitDiffViewer.js';
import { FullFileViewer } from './components/FullFileViewer.js';
import { Minimap } from './components/Minimap.js';
import { CompletionScreen } from './components/CompletionScreen.js';
import { CommandPalette } from './components/CommandPalette.js';
import { PreviewViewer, isPreviewable } from './components/PreviewViewer.js';
import { AgentStatusBar } from './components/AgentStatusBar.js';
import { AgentConfirmDialog } from './components/AgentConfirmDialog.js';
import { AgentTerminal } from './components/AgentTerminal.js';
import { CommentsPanel } from './components/CommentsPanel.js';
import { FileFilterBar } from './components/FileFilterBar.js';
import { GoToLineDialog } from './components/GoToLineDialog.js';
import { SearchDialog } from './components/SearchDialog.js';
import { DiffSkeleton, EmptyState } from './components/EmptyState.js';
import { nearestNewLine, isOpen } from './lib/utils.js';
import { safeFetch, sendJson } from './lib/api.js';
import { useLiveEvents } from './lib/useLiveEvents.js';
import { useComments } from './lib/useComments.js';
import { useKeyboard } from './lib/useKeyboard.js';
import { useAgent } from './lib/useAgent.js';
import { useDiffScroll } from './lib/useDiffScroll.js';
import { useCopyActions } from './lib/useCopyActions.js';
import { useDiffSearch } from './lib/useDiffSearch.js';
import { useAppearance } from './lib/useAppearance.js';
import { useSessionSave } from './lib/useSessionSave.js';

const html = htm.bind(h);

function App() {
  const [repos, setRepos] = useState([]);
  const [files, setFiles] = useState([]);
  const [activeFile, setActiveFile] = useState(null);
  const [diffData, setDiffData] = useState(null);
  const [view, setView] = useState('all');
  const [emptyReason, setEmptyReason] = useState(null);
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
  const [groupMode, setGroupMode] = useState('dir');
  const [showBlame, setShowBlame] = useState(false);
  const [showCommentsPanel, setShowCommentsPanel] = useState(false);
  const [showFileFilter, setShowFileFilter] = useState(false);
  const [fileFilter, setFileFilter] = useState('');
  const [diffMode, setDiffMode] = useState('unified');
  const [contextLines, setContextLines] = useState(3);
  const [showCompletion, setShowCompletion] = useState(false);
  const [showCommandPalette, setShowCommandPalette] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [showGoToLine, setShowGoToLine] = useState(false);
  const [showRepoSearch, setShowRepoSearch] = useState(false);
  const [browsing, setBrowsing] = useState(false);
  const [fileLine, setFileLine] = useState(null);
  const [ignoreWhitespace, setIgnoreWhitespace] = useState(false);
  const [collapseAll, setCollapseAll] = useState(null);
  const [fontSize, setFontSize] = useState(13);
  const [wordWrap, setWordWrap] = useState(false);
  const [keybindings, setKeybindings] = useState({});
  const [commentsPulse, setCommentsPulse] = useState(false);
  const diffRef = useRef(null);
  const diffCache = useRef(new Map());
  const blameCache = useRef(new Map());
  const scrollPositions = useRef(new Map());
  const hoveredLineRef = useRef(null);
  const scrollToLineRef = useRef(null);
  const searchJumpRef = useRef(null);
  const activeFileRef = useRef(activeFile);
  activeFileRef.current = activeFile;
  const commentsRef = useRef(comments);
  commentsRef.current = comments;
  const viewRef = useRef(view);
  viewRef.current = view;
  const contextRef = useRef(contextLines);
  contextRef.current = contextLines;
  const branchRef = useRef(branch);
  branchRef.current = branch;
  const visibleFilesRef = useRef([]);
  const browsingRef = useRef(false);
  browsingRef.current = browsing;
  const showCompletionRef = useRef(false);
  const dialogOpenRef = useRef(false);
  const ignoreWsRef = useRef(false);
  ignoreWsRef.current = ignoreWhitespace;
  const sortByRiskRef = useRef(false);
  sortByRiskRef.current = sortByRisk;

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
    const currentView = v || viewRef.current;
    const res = await safeFetch(`/api/files?view=${currentView}`);
    const data = await res.json();
    setFiles(data);
    if (currentView === 'last-turn' && data.length === 0) {
      setEmptyReason((await (await safeFetch('/api/last-turn')).json()).reason);
    } else {
      setEmptyReason(null);
    }
    const current = activeFileRef.current;
    const inDiff = data.some(f => f.path === current);
    if (inDiff) setBrowsing(false);
    if (data.length > 0 && !browsingRef.current && !inDiff) {
      const firstUnreviewed = data.find(f => !f.reviewed);
      const newActive = (firstUnreviewed || data[0]).path;
      setActiveFile(newActive);
      fetchDiff(newActive);
    }
    setLoading(false);
  }, [fetchDiff]);

  const { saveScrollPosition, scrollToLineAndFlash, scrollToHunk } = useDiffScroll({ diffRef, activeFile, activeFileRef, diffData, scrollPositions, scrollToLineRef, searchJumpRef });

  useEffect(() => {
    Promise.all([fetchTheme(), fetchRepos(), fetchBranch(), fetchCommits(), fetchFiles(), fetchComments()]).then(async () => {
      const [session, settings] = await Promise.all(['/api/session', '/api/settings'].map(u => fetch(u).then(r => r.json()))).catch(() => []);
      if (!session) return;
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
    });
  }, []);

  useAppearance({ themeCss, fontSize, wordWrap });

  const commentsPulseTimer = useRef(null);
  const handleLiveEvents = useCallback((events) => {
    if (events.includes('git_changed') || events.includes('files_changed')) {
      diffCache.current.clear();
      blameCache.current.clear();
      saveScrollPosition();
      fetchFiles();
      fetchCommits();
      fetchRepos();
      if (activeFileRef.current) fetchDiff(activeFileRef.current);
    }
    if (events.includes('comments_changed')) {
      fetchComments();
      fetchFiles();
      setCommentsPulse(true);
      clearTimeout(commentsPulseTimer.current);
      commentsPulseTimer.current = setTimeout(() => setCommentsPulse(false), 2000);
    }
  }, [fetchFiles, fetchCommits, fetchRepos, fetchComments, fetchDiff, saveScrollPosition]);
  const wsConnected = useLiveEvents(handleLiveEvents);

  useEffect(() => {
    const repoInterval = setInterval(fetchRepos, 30000);
    return () => { clearInterval(repoInterval); clearTimeout(commentsPulseTimer.current); };
  }, []);

  const handleViewChange = useCallback(async (newView) => {
    setView(newView);
    setActiveFile(null);
    setBrowsing(false);
    setDiffData(null);
    diffCache.current.clear();
    scrollPositions.current.clear();
    await fetchFiles(newView);
  }, [fetchFiles]);

  const handleRepoSwitch = useCallback(async (index) => {
    setLoading(true);
    await sendJson('/api/repo/switch', 'POST', { index });
    setActiveFile(null);
    setBrowsing(false);
    setDiffData(null);
    setView('all');
    diffCache.current.clear();
    scrollPositions.current.clear();
    await Promise.all([fetchRepos(), fetchBranch(), fetchCommits(), fetchFiles('all'), fetchComments()]);
    setLoading(false);
  }, [fetchRepos, fetchBranch, fetchCommits, fetchFiles, fetchComments]);

  const handleFileSelect = useCallback((path) => {
    saveScrollPosition();
    setActiveFile(path);
    setBrowsing(false);
    setFileLine(null);
    fetchDiff(path);
  }, [fetchDiff, saveScrollPosition]);

  const handleSearchOpen = useCallback(({ path, line, changed }) => {
    setShowRepoSearch(false);
    if (!changed) {
      saveScrollPosition();
      setActiveFile(path);
      setDiffData(null);
      setBrowsing(true);
      setFileLine(line);
      return;
    }
    const opening = path !== activeFileRef.current || browsingRef.current;
    if (opening) handleFileSelect(path);
    if (!line) return;
    if (diffMode === 'file') setFileLine(line);
    else if (opening) searchJumpRef.current = { path, line };
    else scrollToLineAndFlash(nearestNewLine(diffData, line));
  }, [diffMode, diffData, handleFileSelect, saveScrollPosition, scrollToLineAndFlash]);

  const handleCommentSelect = useCallback((filePath, lineIndex) => {
    scrollToLineRef.current = lineIndex;
    handleFileSelect(filePath);
  }, [handleFileSelect]);

  const handleToggleReview = useCallback(async () => {
    const af = activeFileRef.current;
    if (!af || browsingRef.current) return;
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

  const { commentActions, handleBulkResolve } = useComments({ fetchComments, fetchFiles, fetchDiff, diffCache, activeFileRef });

  const handleOpenInEditor = useCallback(async (filePath, lineNum) => {
    await sendJson('/api/editor/open', 'POST', { file_path: filePath, line_num: lineNum });
  }, []);

  const handleSettingsChange = useCallback(async (settings) => {
    if (settings.font_size !== undefined) setFontSize(settings.font_size);
    if (settings.word_wrap !== undefined) setWordWrap(settings.word_wrap);
    if (settings.keybindings !== undefined) setKeybindings(settings.keybindings);
    const res = await sendJson('/api/settings', 'PUT', settings);
    const data = await res.json();
    if (data.css) setThemeCss(data.css);
  }, []);

  const handleSortByRisk = useCallback(() => {
    const next = !sortByRiskRef.current;
    sortByRiskRef.current = next;
    setSortByRisk(next);
    showToast(next ? 'Sorted by risk' : 'Default file order');
  }, []);

  const { agentRunning, taskStatus, setTaskStatus, explainRunning, showAgentConfirm, setShowAgentConfirm, showAgentTerminal, agentCliName,
    handleSendToAgent, handleConfirmAgent, handleCloseTerminal, handleExplain } = useAgent({ commentsRef });

  const { handleCopyPath, handleExportSummary, handleCopyGitLabLink } = useCopyActions({ activeFileRef, branchRef, hoveredLineRef });

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
    const next = !ignoreWsRef.current;
    ignoreWsRef.current = next;
    setIgnoreWhitespace(next);
    showToast(next ? 'Hiding whitespace changes' : 'Showing whitespace changes');
    diffCache.current.clear();
    const af = activeFileRef.current;
    if (af) fetchDiff(af, undefined, next);
  }, [fetchDiff]);

  const handleCollapseAll = useCallback((action) => {
    setCollapseAll({ action });
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
    for (const [filePath, fileComments] of Object.entries(commentsRef.current)) {
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

  const { searchMatchCount, navigateSearchMatch } = useDiffSearch({ searchTerm, searchMatchIndex, setSearchMatchIndex, diffData, diffRef });

  const visibleFiles = useMemo(() => {
    let filtered = (showReviewed ? files : files.filter(f => !f.reviewed)).filter(f => !f.ignored);
    if (fileFilter) {
      const lower = fileFilter.toLowerCase();
      filtered = filtered.filter(f => f.path.toLowerCase().includes(lower));
    }
    return treeOrder(filtered, groupMode, sortByRisk);
  }, [files, showReviewed, sortByRisk, fileFilter, groupMode]);
  const previewing = showPreview && !!activeFile && !browsing && isPreviewable(activeFile);
  const activeFileReviewed = useMemo(() => files.find(f => f.path === activeFile)?.reviewed, [files, activeFile]);

  visibleFilesRef.current = visibleFiles;

  const activeFileOpenComments = useMemo(
    () => (comments[activeFile] || []).filter(isOpen).length,
    [comments, activeFile],
  );
  const activeStats = diffData && diffData.file_path === activeFile ? { adds: diffData.adds, dels: diffData.dels } : null;

  const reviewedCount = useMemo(() => files.filter(f => f.reviewed).length, [files]);
  const commentStats = useMemo(() => {
    let total = 0, open = 0;
    for (const arr of Object.values(comments || {})) {
      total += arr.length;
      open += arr.filter(isOpen).length;
    }
    return { total, open };
  }, [comments]);

  useSessionSave({ activeFile, diffMode, showFileTree, showReviewed, scrollPositions, browsingRef });

  showCompletionRef.current = showCompletion;
  dialogOpenRef.current = showSettings || showSearch || showFileFilter || showShortcuts || showCommandPalette || showGoToLine || showRepoSearch;
  const prevReviewedRef = useRef(null);
  useEffect(() => {
    if (prevReviewedRef.current !== null && files.length > 0
        && reviewedCount === files.length
        && prevReviewedRef.current < files.length) {
      setShowCompletion(true);
    }
    prevReviewedRef.current = reviewedCount;
  }, [reviewedCount, files.length]);

  const { paletteCommands, handleCommand } = useKeyboard({
    keybindings, fontSize, wordWrap,
    showCompletionRef, dialogOpenRef, visibleFilesRef, activeFileRef,
    handleFileSelect, handleToggleReview, handleCopyPath, handleSortByRisk, handleExportSummary,
    handleCopyGitLabLink, handleNextUnreviewed, navigateComment, scrollToHunk, handleToggleWhitespace,
    handleExpandContext, handleCollapseAll, handleSettingsChange, handleBulkResolve, handleSendToAgent, handleExplain,
    setDiffMode, setFileFilter, setSearchTerm, setShowCommandPalette, setShowCompletion, setShowFileFilter,
    setShowFileTree, setShowGoToLine, setShowRepoSearch, setShowReviewed, setShowSearch, setShowSettings, setShowShortcuts
  });

  return html`
    <${TopBar}
      repos=${repos}
      branch=${branch}
      commits=${commits}
      view=${view}
      fileCount=${files.length}
      reviewedCount=${reviewedCount}
      files=${files}
      openCommentCount=${commentStats.open}
      onViewChange=${handleViewChange}
      onRepoSwitch=${handleRepoSwitch}
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
      onShowShortcuts=${() => setShowShortcuts(v => !v)}
      wsConnected=${wsConnected}
      keybindings=${keybindings}
      commentsPulse=${commentsPulse}
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
    <div class="main-content">
      ${showFileTree && html`
        <${FileTree}
          files=${visibleFiles}
          activeFile=${activeFile}
          groupMode=${groupMode}
          sortByRisk=${sortByRisk}
          onGroupModeChange=${setGroupMode}
          onSelect=${handleFileSelect}
          onClose=${() => setShowFileTree(false)}
          commentsPulse=${commentsPulse}
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
      <div class="diff-pane">
        <${FileHeader}
          activeFile=${activeFile}
          stats=${activeStats}
          reviewed=${activeFileReviewed}
          diffMode=${diffMode}
          onDiffModeChange=${setDiffMode}
          ignoreWhitespace=${ignoreWhitespace}
          onToggleWhitespace=${handleToggleWhitespace}
          showReviewed=${showReviewed}
          onToggleShowReviewed=${() => setShowReviewed(v => !v)}
          showBlame=${showBlame}
          onToggleBlame=${() => setShowBlame(v => !v)}
          contextLines=${contextLines}
          onExpandContext=${handleExpandContext}
          openCommentCount=${activeFileOpenComments}
          onBulkResolve=${() => handleBulkResolve(activeFile)}
          onToggleReview=${handleToggleReview}
          previewing=${previewing}
          browsing=${browsing}
          onTogglePreview=${() => setShowPreview(v => !v)}
          keybindings=${keybindings}
        />
        <div class="diff-body">
          ${loading
            ? html`<${DiffSkeleton} />`
            : !activeFile
              ? html`<${EmptyState} files=${files} visibleFiles=${visibleFiles} fileFilter=${fileFilter} showReviewed=${showReviewed} emptyReason=${emptyReason} />`
              : previewing
                ? html`<${PreviewViewer} containerRef=${diffRef} filePath=${activeFile} />`
                : browsing || diffMode === 'file'
                ? html`<${FullFileViewer} containerRef=${diffRef} filePath=${activeFile} view=${view} gotoLine=${fileLine} readOnly=${browsing} />`
                : diffMode === 'split' && diffData
                  ? html`<${SplitDiffViewer}
                      containerRef=${diffRef}
                      data=${diffData}
                      comments=${comments}
                      actions=${commentActions}
                    />`
                  : diffData
                    ? html`<${DiffViewer}
                        containerRef=${diffRef}
                        data=${diffData}
                        comments=${comments}
                        searchTerm=${searchTerm}
                        actions=${commentActions}
                        onOpenInEditor=${handleOpenInEditor}
                        onLineHover=${(num) => { hoveredLineRef.current = num; }}
                        showBlame=${showBlame}
                        blameCache=${blameCache}
                        collapseAll=${collapseAll}
                      />`
                    : html`<${DiffSkeleton} />`
          }
          ${diffMode === 'unified' && diffData && !browsing && html`
            <${Minimap} diffData=${diffData} comments=${comments} containerRef=${diffRef} />
          `}
        </div>
      </div>
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
    ${showRepoSearch && html`
      <${SearchDialog}
        view=${view}
        onOpen=${handleSearchOpen}
        onClose=${() => setShowRepoSearch(false)}
      />
    `}
    ${showAgentTerminal && html`
      <${AgentTerminal}
        onClose=${handleCloseTerminal}
        agentCli=${agentCliName}
      />
    `}
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
        paneAgent=${showAgentConfirm.pane_agent}
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
