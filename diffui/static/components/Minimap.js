import { h } from 'preact';
import { useState, useEffect, useMemo } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

function MinimapMarks({ diffData, comments }) {
  const marks = useMemo(() => {
    const allLines = diffData?.hunks?.flatMap(h => h.lines) || [];
    const totalLines = allLines.length;
    if (!totalLines) return [];
    const filePath = diffData?.file_path;
    const commentLineSet = new Set((comments?.[filePath] || []).map(c => c.line_index));
    const result = [];
    for (let i = 0; i < allLines.length; i++) {
      const line = allLines[i];
      let cls = '';
      if (line.type === 'add') cls = 'minimap-add';
      else if (line.type === 'remove') cls = 'minimap-del';
      else if (commentLineSet.has(line.index)) cls = 'minimap-comment';
      else continue;
      result.push({ cls, top: (i / totalLines) * 100 });
    }
    return result;
  }, [diffData, comments]);

  return marks.map((m, i) => html`<div key=${i} class=${'minimap-mark ' + m.cls} style="top: ${m.top}%"></div>`);
}

export function Minimap({ diffData, comments, containerRef }) {
  const [viewport, setViewport] = useState({ top: 0, height: 0 });

  useEffect(() => {
    const container = containerRef?.current;
    if (!container) return;
    let raf = 0;
    const update = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const { scrollTop, scrollHeight, clientHeight } = container;
        const ratio = clientHeight / scrollHeight;
        setViewport({ top: (scrollTop / scrollHeight) * 100, height: ratio * 100 });
      });
    };
    update();
    container.addEventListener('scroll', update, { passive: true });
    return () => { container.removeEventListener('scroll', update); cancelAnimationFrame(raf); };
  }, [containerRef, diffData]);

  const handleClick = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = (e.clientY - rect.top) / rect.height;
    const container = containerRef?.current;
    if (container) container.scrollTop = pct * container.scrollHeight;
  };

  const totalLines = diffData?.hunks?.reduce((s, h) => s + h.lines.length, 0) || 0;
  if (!totalLines) return null;

  return html`
    <div class="minimap" onClick=${handleClick}>
      <div class="minimap-viewport" style="top: ${viewport.top}%; height: ${Math.max(viewport.height, 2)}%"></div>
      <${MinimapMarks} diffData=${diffData} comments=${comments} />
    </div>
  `;
}
