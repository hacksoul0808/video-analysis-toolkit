// ═══════════════════════════════════════
// API Layer
// ═══════════════════════════════════════

export const API = {
  async get(u) {
    const r = await fetch(u);
    if (!r.ok) throw new Error((await r.json().catch(() => ({ error: r.statusText }))).error);
    return r.json();
  },

  async post(u, d) {
    const r = await fetch(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(d) });
    if (!r.ok) throw new Error((await r.json().catch(() => ({ error: r.statusText }))).error);
    return r.json();
  },

  library(t, s, q) {
    return API.get('/api/library?sort=' + s + (t ? '&tag=' + encodeURIComponent(t) : '') + (q ? '&q=' + encodeURIComponent(q) : ''));
  },

  stats() { return API.get('/api/stats'); },

  methodology(t) { return API.get('/api/methodology' + (t ? '?tag=' + encodeURIComponent(t) : '')); },

  process(d) { return API.post('/api/process', d); },

  analyze(d) { return API.post('/api/analyze', d); },

  report(id) { return fetch('/api/video/report/' + id).then(r => r.text()); },

  transcript(id) { return API.get('/api/video/transcript/' + id); },

  analysis(id) { return API.get('/api/video/analysis/' + id); },

  refreshMetrics(ids) { return API.post('/api/refresh-metrics', ids ? { video_ids: ids } : {}); },
};
