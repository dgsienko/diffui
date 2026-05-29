import { h } from 'preact';
import { useState, useEffect } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

export function Minimap({ diffData, comments, containerRef }) {
  const [viewport, setViewport] = useState({ top: 0, height: 0 });

  const allLines = diffData?.hunks?.flatMap(h => h.lines) || [];
  const totalLines = allLines.length;
  if (!totalLines) return null;

  const filePath = diffData?.file_path;
  const fileComments = comments?.[filePath] || [];
  const commentLineSet = new Set(fileComments.map(c => c.line_index));

  useEffect(() => {
    const container = containerRef?.current;
    if (!container) return;
    const update = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      const ratio = clientHeight / scrollHeight;
      setViewport({ top: (scrollTop / scrollHeight) * 100, height: ratio * 100 });
    };
    update();
    container.addEventListener('scroll', update, { passive: true });
    return () => container.removeEventListener('scroll', update);
  }, [containerRef, diffData]);

  const handleClick = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = (e.clientY - rect.top) / rect.height;
    const container = containerRef?.current;
    if (container) container.scrollTop = pct * container.scrollHeight;
  };

  return html`
    <div class="minimap" onClick=${handleClick}>
      <div class="minimap-viewport" style="top: ${viewport.top}%; height: ${Math.max(viewport.height, 2)}%"></div>
      ${allLines.map((line, i) => {
        const top = (i / totalLines) * 100;
        let cls = '';
        if (line.type === 'add') cls = 'minimap-add';
        else if (line.type === 'remove') cls = 'minimap-del';
        else if (commentLineSet.has(line.index)) cls = 'minimap-comment';
        else return null;
        return html`<div class=${'minimap-mark ' + cls} style="top: ${top}%"></div>`;
      })}
    </div>
  `;
}
