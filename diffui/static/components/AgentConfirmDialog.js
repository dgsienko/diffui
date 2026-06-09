import { h } from 'preact';
import htm from 'htm';

const html = htm.bind(h);

export function AgentConfirmDialog({ agentCli, commentCount, onConfirm, onCancel }) {
  return html`
    <div class="settings-overlay" onClick=${(e) => { if (e.target.classList.contains('settings-overlay')) onCancel(); }}>
      <div class="agent-confirm-dialog">
        <div class="agent-confirm-title">Send to agent</div>
        <div class="agent-confirm-body">
          <p>This will spawn <strong>${agentCli || 'your configured agent'}</strong> to address <strong>${commentCount || 'the'} open comment${commentCount === 1 ? '' : 's'}</strong>.</p>
          <p>The agent will:</p>
          <ul>
            <li>Read the diff and each comment in context</li>
            <li>Make fixes and reply to comments explaining what it did</li>
            <li>Ask clarifying questions for anything unclear</li>
            <li>Leave unresolved comments in place</li>
          </ul>
          <p>Changes will appear in real-time as the agent works.</p>
        </div>
        <div class="agent-confirm-actions">
          <button class="comment-cancel-btn" onClick=${onCancel}>Cancel</button>
          <button class="comment-submit-btn" onClick=${onConfirm}>Start agent</button>
        </div>
      </div>
    </div>
  `;
}
