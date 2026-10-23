import { h } from 'preact';
import htm from 'htm';

const html = htm.bind(h);

export function AgentConfirmDialog({ agentCli, paneAgent, commentCount, onConfirm, onCancel }) {
  const comments = html`<strong>${commentCount || 'the'} open comment${commentCount === 1 ? '' : 's'}</strong>`;
  return html`
    <div class="settings-overlay" onClick=${(e) => { if (e.target.classList.contains('settings-overlay')) onCancel(); }}>
      <div class="agent-confirm-dialog">
        <div class="agent-confirm-title">Send to agent</div>
        <div class="agent-confirm-body">
          ${paneAgent
            ? html`<p>This will paste a prompt for ${comments} into your <strong>${paneAgent}</strong> pane. Press Enter there to send it.</p>`
            : html`<p>This will spawn <strong>${agentCli || 'your configured agent'}</strong> to address ${comments}.</p>`}
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
          <button class="btn" onClick=${onCancel}>Cancel</button>
          <button class="btn btn-primary" onClick=${() => onConfirm(paneAgent)}>${paneAgent ? 'Paste into pane' : 'Start agent'}</button>
        </div>
      </div>
    </div>
  `;
}
