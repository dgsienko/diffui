import { h } from 'preact';
import { useEffect, useRef } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

function tabDir(path) {
  const parts = path.split('/');
  return parts.length > 1 ? parts.slice(0, -1).join('/') + '/' : '';
}

function tabTitle(f) {
  const parts = [f.path];
  const counts = [];
  if (f.adds) counts.push('+' + f.adds);
  if (f.dels) counts.push('−' + f.dels);
  if (counts.length) parts.push(counts.join(' '));
  if (f.risk_level === 'medium' || f.risk_level === 'high') {
    parts.push(f.risk_level.charAt(0).toUpperCase() + f.risk_level.slice(1) + ' risk');
  }
  return parts.join(' — ');
}

export function FileTabs({ files, activeFile, onSelect }) {
  const activeRef = useRef(null);
  const wrapRef = useRef(null);
  const barRef = useRef(null);

  useEffect(() => {
    if (activeRef.current) {
      activeRef.current.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    }
  }, [activeFile]);

  useEffect(() => {
    const wrap = wrapRef.current;
    const bar = barRef.current;
    if (!wrap || !bar) return;
    const update = () => {
      const overflow = bar.scrollWidth - bar.clientWidth;
      wrap.classList.toggle('at-start', bar.scrollLeft <= 1);
      wrap.classList.toggle('at-end', bar.scrollLeft >= overflow - 1);
    };
    update();
    bar.addEventListener('scroll', update, { passive: true });
    const ro = new ResizeObserver(update);
    ro.observe(bar);
    return () => {
      bar.removeEventListener('scroll', update);
      ro.disconnect();
    };
  }, [files]);

  if (!files.length) return null;

  return html`
    <div class="tab-bar-wrap" ref=${wrapRef}>
    <div class="tab-bar" role="tablist" ref=${barRef}>
      ${files.map(f => html`
        <div
          ref=${f.path === activeFile ? activeRef : null}
          class=${'tab' + (f.path === activeFile ? ' active' : '') + (f.reviewed ? ' reviewed' : '')}
          role="tab"
          tabindex=${f.path === activeFile ? '0' : '-1'}
          aria-selected=${f.path === activeFile}
          onClick=${() => onSelect(f.path)}
          onKeyDown=${(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(f.path); } }}
          title=${tabTitle(f)}
        >
          ${f.risk_level && f.risk_level !== 'low' && html`<span class=${'risk-dot risk-' + f.risk_level} title=${'Risk: ' + f.risk_level}></span>`}
          ${f.reviewed ? '✓ ' : ''}
          ${f.path === activeFile && tabDir(f.path) ? html`<span class="tab-dir">${tabDir(f.path)}</span>` : ''}${f.short_name}
          ${f.comment_count > 0 ? html` <span style="color: var(--accent)">(${f.comment_count})</span>` : ''}
        </div>
      `)}
    </div>
    </div>
  `;
}
