import { h } from 'preact';
import { useState, useEffect, useCallback } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

let _showToast = null;

export function showToast(message, type = 'info') {
  if (_showToast) _showToast(message, type);
}

export function ToastContainer() {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((message, type) => {
    const id = Date.now() + Math.random();
    setToasts(t => [...t, { id, message, type }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 3000);
  }, []);

  useEffect(() => {
    _showToast = addToast;
    return () => { _showToast = null; };
  }, [addToast]);

  if (!toasts.length) return null;

  return html`
    <div class="toast-container">
      ${toasts.map(t => html`
        <div key=${t.id} class=${'toast toast-' + t.type}>${t.message}</div>
      `)}
    </div>
  `;
}
