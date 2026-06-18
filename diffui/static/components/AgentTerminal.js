import { h } from 'preact';
import { useEffect, useRef, useState, useCallback } from 'preact/hooks';
import htm from 'htm';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { useResize } from '../lib/utils.js';

const html = htm.bind(h);

function formatElapsed(s) {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
}

export function AgentTerminal({ onClose, agentCli }) {
  const containerRef = useRef(null);
  const termRef = useRef(null);
  const fitRef = useRef(null);
  const wsRef = useRef(null);
  const { ref: panelRef, size: height, onResizeStart } = useResize(320, 120, () => Math.floor(window.innerHeight * 0.8), 'y');
  const [status, setStatus] = useState('connecting');
  const statusRef = useRef(status);
  statusRef.current = status;
  const [exitCode, setExitCode] = useState(null);
  const [startTime] = useState(Date.now());
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      if (statusRef.current === 'running' || statusRef.current === 'connecting') {
        setElapsed(Math.floor((Date.now() - startTime) / 1000));
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [startTime]);

  useEffect(() => {
    if (!containerRef.current) return;

    const root = document.documentElement;
    const cs = getComputedStyle(root);

    const term = new Terminal({
      theme: {
        background: cs.getPropertyValue('--bg-dark').trim() || '#181825',
        foreground: cs.getPropertyValue('--fg').trim() || '#cdd6f4',
        cursor: cs.getPropertyValue('--accent').trim() || '#89b4fa',
        selectionBackground: cs.getPropertyValue('--hover-bg').trim() || '#313244',
      },
      fontFamily: "'SF Mono', 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace",
      fontSize: parseInt(cs.getPropertyValue('--code-font-size')) || 13,
      cursorBlink: true,
      convertEol: true,
      scrollback: 10000,
    });

    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(containerRef.current);

    requestAnimationFrame(() => fit.fit());

    termRef.current = term;
    fitRef.current = fit;

    const wsProto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${wsProto}//${location.host}/api/agent/ws`);
    wsRef.current = ws;

    ws.onopen = () => {
      const dims = fit.proposeDimensions();
      if (dims) {
        ws.send(JSON.stringify({ type: 'resize', rows: dims.rows, cols: dims.cols }));
      }
    };

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'output') {
          term.write(msg.data);
        } else if (msg.type === 'started') {
          setStatus('running');
        } else if (msg.type === 'exit') {
          setStatus('exited');
          setExitCode(msg.code);
          setElapsed(Math.floor((Date.now() - startTime) / 1000));
        } else if (msg.type === 'idle') {
          setStatus('idle');
          setElapsed(Math.floor((Date.now() - startTime) / 1000));
        } else if (msg.type === 'error') {
          setStatus('error');
          term.write(`\r\n\x1b[31mError: ${msg.message}\x1b[0m\r\n`);
        }
      } catch {}
    };

    ws.onclose = () => {
      if (status !== 'exited') {
        term.write('\r\n\x1b[33m[Connection closed]\x1b[0m\r\n');
      }
    };

    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'stdin', data }));
        if (statusRef.current === 'idle') setStatus('running');
      }
    });

    const resizeObserver = new ResizeObserver(() => {
      requestAnimationFrame(() => {
        fit.fit();
        const dims = fit.proposeDimensions();
        if (dims && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'resize', rows: dims.rows, cols: dims.cols }));
        }
      });
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      ws.close();
      term.dispose();
      termRef.current = null;
      fitRef.current = null;
      wsRef.current = null;
    };
  }, []);

  const handleKill = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'kill' }));
    }
  }, []);

  const statusLabel = status === 'connecting' ? 'Connecting...'
    : status === 'running' ? `${agentCli || 'Agent'} running`
    : status === 'idle' ? 'Done — waiting for input'
    : status === 'exited' ? (exitCode === 0 ? 'Completed' : `Failed (exit ${exitCode})`)
    : 'Error';

  const statusClass = status === 'exited'
    ? (exitCode === 0 ? 'status-done' : 'status-failed')
    : status === 'idle' ? 'status-done'
    : '';

  return html`
    <div class=${'agent-terminal-panel ' + statusClass} ref=${panelRef} style="height: ${height}px">
      <div class="agent-terminal-resize" onMouseDown=${onResizeStart}></div>
      <div class="agent-terminal-header">
        <div class="agent-terminal-header-left">
          ${status === 'running' && html`<span class="agent-status-spinner"></span>`}
          <span class="agent-terminal-title">${statusLabel}</span>
          <span class="agent-terminal-elapsed">${formatElapsed(elapsed)}</span>
        </div>
        <div class="agent-terminal-header-right">
          ${status === 'running' && html`
            <button class="agent-terminal-btn" onClick=${handleKill} title="Stop agent">Stop</button>
          `}
          <button class="agent-terminal-btn" onClick=${onClose} title="Close terminal">Close</button>
        </div>
      </div>
      <div class="agent-terminal-body" ref=${containerRef}></div>
    </div>
  `;
}
