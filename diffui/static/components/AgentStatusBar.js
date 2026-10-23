import { h } from 'preact';
import { useState, useEffect } from 'preact/hooks';
import htm from 'htm';
import { formatDuration } from '../lib/utils.js';

const html = htm.bind(h);

export function AgentStatusBar({ task, onDismiss }) {
  const [, setTick] = useState(0);

  useEffect(() => {
    if (task.status !== 'running') return;
    const id = setInterval(() => setTick(t => t + 1), 1000);
    return () => clearInterval(id);
  }, [task.status]);

  const isRunning = task.status === 'running';
  const isDone = task.status === 'done';
  const isFailed = task.status === 'failed';

  return html`
    <div class=${'agent-status-bar' + (isDone ? ' status-done' : isFailed ? ' status-failed' : '')}>
      <div class="agent-status-content">
        <span class="agent-status-indicator">
          ${isRunning ? html`<span class="agent-status-spinner"></span>` : isDone ? '✓' : '✕'}
        </span>
        <span class="agent-status-label">
          ${isRunning ? task.label
            : task.message?.url ? html`${task.message.text} — <a class="agent-status-link" href=${task.message.url} target="_blank">${task.message.url}</a>`
            : (task.message || task.label)}
        </span>
        <span class="agent-status-elapsed">
          ${formatDuration(isRunning ? Date.now() - task.startTime : (task.endTime || Date.now()) - task.startTime)}
        </span>
      </div>
      ${!isRunning && html`
        <button class="agent-status-dismiss" onClick=${onDismiss}>✕</button>
      `}
    </div>
  `;
}
