import { h } from 'preact';
import htm from 'htm';

const html = htm.bind(h);

export function DiffStatsBar({ files }) {
  if (!files.length) return null;

  const totalAdds = files.reduce((s, f) => s + (f.adds || 0), 0);
  const totalDels = files.reduce((s, f) => s + (f.dels || 0), 0);
  const maxChange = Math.max(...files.map(f => (f.adds || 0) + (f.dels || 0)), 1);

  return html`
    <div class="stats-bar">
      <span class="stats-total">
        <span class="stats-add">+${totalAdds}</span>
        <span class="stats-del">-${totalDels}</span>
      </span>
      <div class="stats-files">
        ${files.map(f => {
          const total = (f.adds || 0) + (f.dels || 0);
          if (!total) return null;
          const width = Math.max((total / maxChange) * 100, 4);
          const addPct = (f.adds || 0) / total * 100;
          return html`
            <div class="stats-file" title="${f.path}: +${f.adds} -${f.dels}" style="width: ${width}%">
              <div class="stats-file-add" style="width: ${addPct}%"></div>
              <div class="stats-file-del" style="width: ${100 - addPct}%"></div>
            </div>
          `;
        })}
      </div>
    </div>
  `;
}
