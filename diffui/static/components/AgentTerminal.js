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
  const wsRef = useRef(null);
  const inputRef = useRef(null);
  const { ref: panelRef, size: height, onResizeStart } = useResize(320, 120, () => Math.floor(window.innerHeight * 0.8), 'y');
  const [status, setStatus] = useState('connecting');
  const statusRef = useRef(status);
  statusRef.current = status;
  const [exitCode, setExitCode] = useState(null);
  const [startTime] = useState(Date.now());
  const [elapsed, setElapsed] = useState(0);
  const [inputValue, setInputValue] = useState('');

  const sendStdin = useCallback((data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'stdin', data }));
    }
  }, []);

  useEffect(() => {
    const SEQS = { ArrowUp: '\x1b[A', ArrowDown: '\x1b[B' };
    const globalArrowHandler = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
      const seq = SEQS[e.key];
      if (seq) {
        e.preventDefault();
        sendStdin(seq);
      }
    };
    document.addEventListener('keydown', globalArrowHandler);
    return () => document.removeEventListener('keydown', globalArrowHandler);
  }, [sendStdin]);

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
      cursorBlink: false,
      convertEol: true,
      disableStdin: true,
      scrollback: 10000,
    });

    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(containerRef.current);
    requestAnimationFrame(() => fit.fit());


    const wsProto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${wsProto}//${location.host}/api/agent/ws`);
    wsRef.current = ws;

    ws.onopen = () => {
      const dims = fit.proposeDimensions();
      ws.send(JSON.stringify({
        type: 'init',
        rows: dims?.rows || 24,
        cols: dims?.cols || 80,
      }));
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
      if (statusRef.current !== 'exited') {
        term.write('\r\n\x1b[33m[Connection closed]\x1b[0m\r\n');
      }
    };

    const doFit = () => {
      requestAnimationFrame(() => {
        fit.fit();
        term.scrollToBottom();
        const dims = fit.proposeDimensions();
        if (dims && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'resize', rows: dims.rows, cols: dims.cols }));
        }
      });
    };

    const resizeObserver = new ResizeObserver(doFit);
    resizeObserver.observe(containerRef.current);

    requestAnimationFrame(() => inputRef.current?.focus());

    return () => {
      resizeObserver.disconnect();
      ws.close();
      term.dispose();
      wsRef.current = null;
    };
  }, []);

  const handleKill = useCallback(async () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'kill' }));
    }
    try {
      await fetch('/api/agent/kill', { method: 'POST' });
    } catch {}
    setStatus('exited');
    setExitCode(-15);
  }, []);

  const handleInputKeyDown = useCallback((e) => {
    if (e.key === 'ArrowUp') { e.preventDefault(); sendStdin('\x1b[A'); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); sendStdin('\x1b[B'); }
    else if (e.key === 'Enter') {
      e.preventDefault();
      if (inputValue) {
        sendStdin(inputValue + '\r');
        setInputValue('');
      } else {
        sendStdin('\r');
      }
    }
  }, [inputValue, sendStdin]);

  const statusLabel = status === 'connecting' ? 'Connecting...'
    : status === 'running' ? `${agentCli || 'Agent'} running`
    : status === 'idle' ? 'Done — waiting for input'
    : status === 'exited' ? (exitCode === 0 ? 'Completed' : `Failed (exit ${exitCode})`)
    : 'Error';

  const statusClass = status === 'exited'
    ? (exitCode === 0 ? 'status-done' : 'status-failed')
    : status === 'idle' ? 'status-done'
    : '';

  const isActive = status === 'running' || status === 'idle';

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
          ${isActive && html`
            <button class="agent-terminal-btn" onClick=${handleKill} title="Stop agent">Stop</button>
          `}
          <button class="agent-terminal-btn" onClick=${onClose} title="Close terminal">Close</button>
        </div>
      </div>
      <div class="agent-terminal-body" ref=${containerRef}></div>
      ${isActive && html`
        <div class="agent-terminal-input-bar">
          <button class="agent-terminal-arrow-btn" onClick=${() => sendStdin('\x1b[A')} title="Arrow Up">▲</button>
          <button class="agent-terminal-arrow-btn" onClick=${() => sendStdin('\x1b[B')} title="Arrow Down">▼</button>
          <input
            ref=${inputRef}
            class="agent-terminal-input"
            type="text"
            placeholder="Type a response and press Enter..."
            value=${inputValue}
            onInput=${(e) => setInputValue(e.target.value)}
            onKeyDown=${handleInputKeyDown}
          />
          <button class="agent-terminal-send-btn" onClick=${() => { sendStdin((inputValue || '') + '\r'); setInputValue(''); }} title="Send">Enter</button>
        </div>
      `}
    </div>
  `;
}
