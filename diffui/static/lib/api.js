export function sendJson(url, method, body) {
  return fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
}

export function commentUrl(filePath, id, suffix = '') {
  return `/api/comments/${encodeURIComponent(filePath)}/${id}${suffix}`;
}
