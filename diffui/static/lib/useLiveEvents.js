import { useState, useEffect } from 'preact/hooks';

// Feeds the server's change events to onEvents: over the WebSocket, falling
// back to SSE once it closes. Returns whether a stream is connected.
export function useLiveEvents(onEvents) {
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let cleanup = () => {};

    const connectSSE = () => {
      setConnected(false);
      const es = new EventSource('/api/events');
      es.onopen = () => setConnected(true);
      es.onerror = () => setConnected(false);
      es.onmessage = (e) => {
        try { onEvents(JSON.parse(e.data).events); } catch {}
      };
      cleanup = () => { es.close(); setConnected(false); };
    };

    const wsProto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProto}//${location.host}/api/ws`;
    const ws = new WebSocket(wsUrl);
    ws.onopen = () => setConnected(true);
    ws.onclose = () => { setConnected(false); connectSSE(); };
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.events) onEvents(msg.events);
      } catch {}
    };
    cleanup = () => { ws.close(); setConnected(false); };

    return () => cleanup();
  }, [onEvents]);

  return connected;
}
