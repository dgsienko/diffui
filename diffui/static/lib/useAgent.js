import { useState, useEffect, useCallback, useRef } from 'preact/hooks';
import { showToast } from '../components/Toast.js';
import { safeFetch } from './api.js';
import { isOpen } from './utils.js';

// The agent terminal flow and the explain-changes task with its status bar.
export function useAgent({ commentsRef }) {
  const pollTimer = useRef(null);
  const dismissTimer = useRef(null);
  useEffect(() => () => { clearInterval(pollTimer.current); clearTimeout(dismissTimer.current); }, []);

  const [taskStatus, setTaskStatus] = useState(null);

  const [agentRunning, setAgentRunning] = useState(false);
  const [showAgentConfirm, setShowAgentConfirm] = useState(null);
  const [showAgentTerminal, setShowAgentTerminal] = useState(false);
  const [agentCliName, setAgentCliName] = useState('agent');

  const handleSendToAgent = useCallback(async () => {
    const hasOpen = Object.values(commentsRef.current).some(arr => arr.some(isOpen));
    if (!hasOpen) { showToast('No open comments to send', 'error'); return; }
    const r = await fetch('/api/agent/prompt', { method: 'POST' });
    const data = await r.json();
    if (!data.ok) { showToast(data.error || 'No comments to address', 'error'); return; }
    setShowAgentConfirm(data);
  }, []);

  const handleConfirmAgent = useCallback(async (paneAgent) => {
    setShowAgentConfirm(null);
    if (paneAgent) {
      const r = await safeFetch('/api/agent/paste', { method: 'POST' });
      const data = await r.json();
      showToast(data.ok ? `Pasted into ${data.agent}. Press Enter there to send.` : data.error, data.ok ? 'success' : 'error');
      return;
    }
    const r = await safeFetch('/api/agent/start', { method: 'POST' });
    const data = await r.json();
    if (!data.ok) { showToast(data.error || 'Failed to start agent', 'error'); return; }
    setAgentCliName(data.agent || 'agent');
    setAgentRunning(true);
    setShowAgentTerminal(true);
  }, []);

  const handleCloseTerminal = useCallback(() => {
    setShowAgentTerminal(false);
    setAgentRunning(false);
  }, []);

  const [explainRunning, setExplainRunning] = useState(false);
  const handleExplain = useCallback(async () => {
    const r = await fetch('/api/explain', { method: 'POST' });
    const data = await r.json();
    if (!data.ok) { showToast(data.error || 'Failed to start', 'error'); return; }
    setExplainRunning(true);
    const label = 'Generating explanation';
    const startTime = Date.now();
    setTaskStatus({ label, startTime, status: 'running' });
    pollTimer.current = setInterval(async () => {
      try {
        const s = await fetch('/api/explain/status');
        const status = await s.json();
        if (!status.running) {
          clearInterval(pollTimer.current);
          setExplainRunning(false);
          const ok = status.exit_code === 0;
          const message = ok ? { text: 'Explanation ready', url: `${location.origin}/api/explain/view` } : 'Explanation generation failed';
          setTaskStatus({ label, startTime, status: ok ? 'done' : 'failed', message, endTime: Date.now() });
          dismissTimer.current = setTimeout(() => setTaskStatus(s => s?.startTime === startTime ? null : s), 10000);
        }
      } catch {
        clearInterval(pollTimer.current);
        setExplainRunning(false);
        setTaskStatus({ label, startTime, status: 'failed', message: 'Lost connection', endTime: Date.now() });
      }
    }, 3000);
  }, []);

  return { agentRunning, taskStatus, setTaskStatus, explainRunning, showAgentConfirm, setShowAgentConfirm, showAgentTerminal, agentCliName,
    handleSendToAgent, handleConfirmAgent, handleCloseTerminal, handleExplain };
}
