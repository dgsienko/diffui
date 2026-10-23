import { h } from 'preact';
import htm from 'htm';

const html = htm.bind(h);

const SKELETON_WIDTHS = ['60%', '80%', '45%', '90%', '70%', '55%', '85%', '40%'];

export function DiffSkeleton() {
  return html`
    <div class="skeleton-lines" aria-label="Loading diff" aria-busy="true">
      ${SKELETON_WIDTHS.map((w, i) => html`<div class="skeleton-line" key=${i} style=${`width: ${w}`}></div>`)}
    </div>
  `;
}

export function EmptyState({ files, visibleFiles, fileFilter, showReviewed, emptyReason }) {
  if (files.length === 0) {
    if (emptyReason) return html`<div class="empty-state"><span class="empty-state-title">No last-turn changes</span><span class="empty-state-hint">${emptyReason}</span></div>`;
    return html`<div class="empty-state"><span class="empty-state-title">No changes on this branch</span><span class="empty-state-hint">This branch has no diff against the merge base</span></div>`;
  }
  if (visibleFiles.length === 0) {
    if (fileFilter) return html`<div class="empty-state"><span class="empty-state-title">No files match your filter</span><span class="empty-state-hint">No files match "${fileFilter}"</span></div>`;
    if (!showReviewed) return html`<div class="empty-state"><span class="empty-state-title">All files reviewed</span><span class="empty-state-hint">Press <kbd>a</kbd> to show reviewed files</span></div>`;
    return html`<div class="empty-state"><span class="empty-state-title">No files to show</span><span class="empty-state-hint">No files match the current view</span></div>`;
  }
  return html`<div class="empty-state"><span class="empty-state-title">Select a file</span><span class="empty-state-hint">Choose a file from the explorer</span></div>`;
}
