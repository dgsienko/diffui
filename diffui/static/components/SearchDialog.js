import { h } from 'preact';
import { useState, useEffect, useRef, useMemo } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

const DEBOUNCE_MS = 150;
const SCOPES = [['changed', 'Changed'], ['all', 'All files']];

function Marked({ text, query }) {
  if (!query) return text;
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return text.split(new RegExp(`(${escaped})`, 'i')).map((part, i) => (i % 2 ? html`<mark>${part}</mark>` : part));
}

function NotInDiff({ changed }) {
  return !changed && html`<span class="repo-search-tag">not in diff</span>`;
}

export function SearchDialog({ view, onOpen, onClose }) {
  const [query, setQuery] = useState('');
  const [scope, setScope] = useState('changed');
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(0);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  useEffect(() => {
    if (inputRef.current) inputRef.current.focus();
  }, []);

  useEffect(() => {
    if (!query) { setData(null); setError(null); return; }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/search?${new URLSearchParams({ q: query, view, scope })}`, { signal: controller.signal });
        if (!res.ok) throw new Error(res.status);
        setData(await res.json());
        setError(null);
      } catch (err) {
        if (err.name !== 'AbortError') { setData(null); setError(`Search failed: ${err.message}`); }
      }
    }, DEBOUNCE_MS);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [query, scope, view]);

  // `items` are the rows Enter can open. `rows` adds the headings between them.
  const { rows, items } = useMemo(() => {
    const rows = [];
    const items = [];
    const add = (item) => { rows.push({ item, idx: items.length }); items.push(item); };
    const files = data?.files || [];
    if (files.length) {
      rows.push({ heading: `Files (${files.length})` });
      for (const f of files) add({ path: f.path, line: null, changed: f.changed });
    }
    let current = null;
    for (const hit of data?.hits || []) {
      if (hit.path !== current) {
        current = hit.path;
        rows.push({ path: current, changed: hit.changed });
      }
      add({ path: hit.path, line: hit.line, text: hit.text.trim(), changed: hit.changed });
    }
    return { rows, items };
  }, [data]);

  useEffect(() => {
    setSelected(0);
    if (listRef.current) listRef.current.scrollTop = 0;
  }, [data]);

  const move = (step) => {
    const next = Math.max(0, Math.min(selected + step, items.length - 1));
    setSelected(next);
    const el = listRef.current && listRef.current.querySelectorAll('.repo-search-item')[next];
    if (el) el.scrollIntoView({ block: 'nearest' });
  };
  const toggleScope = () => setScope(s => (s === 'changed' ? 'all' : 'changed'));

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      onClose();
    } else if (e.key === 'Tab') {
      e.preventDefault();
      toggleScope();
    } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'PageDown' || e.key === 'PageUp') {
      e.preventDefault();
      move((e.key.endsWith('Down') ? 1 : -1) * (e.key.startsWith('Page') ? 10 : 1));
    } else if (e.key === 'Enter' && items[selected]) {
      onOpen(items[selected]);
    }
  };

  const itemClass = (idx, changed) => 'command-palette-item repo-search-item' + (idx === selected ? ' selected' : '') + (changed ? '' : ' dim');

  return html`
    <div class="command-palette-overlay" onClick=${(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div class="command-palette repo-search" role="dialog" aria-label="Search">
        <div class="repo-search-head">
          <input
            ref=${inputRef}
            class="command-palette-input"
            type="text"
            placeholder="File name or text..."
            value=${query}
            onInput=${(e) => setQuery(e.target.value)}
            onKeyDown=${handleKeyDown}
          />
          <div class="segmented">
            ${SCOPES.map(([val, label]) => html`
              <button class=${'segmented-btn' + (scope === val ? ' active' : '')} onClick=${() => { setScope(val); inputRef.current.focus(); }}>${label}</button>
            `)}
          </div>
        </div>
        <div class="command-palette-list" ref=${listRef}>
          ${rows.map(row => row.heading
            ? html`<div class="command-palette-category">${row.heading}</div>`
            : !row.item
              ? html`<div class=${'repo-search-heading' + (row.changed ? '' : ' dim')}>${row.path}<${NotInDiff} changed=${row.changed} /></div>`
              : html`
                <div
                  class=${itemClass(row.idx, row.item.changed)}
                  onClick=${() => onOpen(row.item)}
                  onMouseEnter=${() => setSelected(row.idx)}
                >
                  ${row.item.line === null
                    ? html`<span class="repo-search-path"><${Marked} text=${row.item.path} query=${query} /></span><${NotInDiff} changed=${row.item.changed} />`
                    : html`<span class="repo-search-line">${row.item.line}</span><span class="repo-search-text"><${Marked} text=${row.item.text} query=${query} /></span>`}
                </div>
              `)}
          ${query && !data && !error && html`<div class="command-palette-empty">Searching...</div>`}
          ${error && html`<div class="command-palette-empty">${error}</div>`}
          ${data && !items.length && html`<div class="command-palette-empty">No matches</div>`}
          ${data?.truncated && html`<div class="command-palette-empty">Showing the first matches only. Narrow the query.</div>`}
        </div>
        <div class="repo-search-hint">enter opens, tab switches Changed and All files, esc closes. Text matches ignore case.</div>
      </div>
    </div>
  `;
}
