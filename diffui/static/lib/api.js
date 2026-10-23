import { showToast } from '../components/Toast.js';

export async function safeFetch(url, opts) {
  try {
    const res = await fetch(url, opts);
    if (!res.ok) throw new Error(`${res.status}`);
    return res;
  } catch (err) {
    showToast(`Request failed: ${url.replace('/api/', '')}`, 'error');
    throw err;
  }
}

export function sendJson(url, method, body) {
  return fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
}

export function commentUrl(filePath, id, suffix = '') {
  return `/api/comments/${encodeURIComponent(filePath)}/${id}${suffix}`;
}
