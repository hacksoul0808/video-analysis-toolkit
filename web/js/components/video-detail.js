// ═══════════════════════════════════════
// Video Detail Modal — player, workflow bar, tab switching, title/tag editing
// ═══════════════════════════════════════

import { API } from '../api.js';
import { Store } from '../store.js';
import { confirm, closeConfirm } from './confirm-modal.js';
import { esc } from '../utils.js';

// ── Detail Tags ───────────────────────────────
function renderDetailTags(v) {
  const row = document.getElementById('detail-tag-row');
  const tags = v.tags || [];
  let h = tags.map(t => '<span class="tag-edit-chip">' + esc(t) + '<span class="tag-x" onclick="event.stopPropagation();removeTagFromVideo(\'' + esc(t) + '\')">&times;</span></span>').join('');
  h += '<input class="tag-add-input" id="detail-tag-input" placeholder="+ 添加标签" onchange="addTagToVideo()" onkeydown="if(event.key===\'Enter\'){addTagToVideo();event.preventDefault()}">';
  row.innerHTML = h;
}

// ── Engagement Metrics ────────────────────────
function formatNum(n) {
  if (n >= 10000) return (n / 10000).toFixed(1) + '万';
  return n.toLocaleString();
}

function calcEngagementScore(metrics) {
  const m = metrics || {};
  const likes = m.likes || 0;
  if (likes <= 0) return 0;
  const comments = m.comments || 0;
  const shares = m.shares || 0;
  const collects = m.collects || 0;

  // 1. 点赞量级分 (0-30): log10 scale
  const likePower = Math.min(Math.log10(likes) * 6, 30);

  // 2. 评论互动率 (0-20): rate = comments/likes
  const commentScore = Math.min((comments / likes) * 500, 20);

  // 3. 分享传播率 (0-25): rate = shares/likes
  const shareScore = Math.min((shares / likes) * 100, 25);

  // 4. 收藏价值率 (0-25): rate = collects/likes
  const collectScore = Math.min((collects / likes) * 50, 25);

  return Math.round(Math.min(likePower + commentScore + shareScore + collectScore, 100));
}

function renderEngagementMetrics(v) {
  const el = document.getElementById('detail-eng-metrics');
  if (!el) return;
  const m = v.metrics || {};
  const likes = m.likes || 0;
  if (!likes && !m.comments && !m.shares && !m.collects) {
    el.innerHTML = '<span style="font-size:.72rem;color:var(--color-text-dim)">暂无互动数据</span>';
    return;
  }
  const engScore = calcEngagementScore(m);
  const items = [
    { label: '点赞', val: likes },
    { label: '评论', val: m.comments || 0 },
    { label: '分享', val: m.shares || 0 },
    { label: '收藏', val: m.collects || 0 },
  ];
  let h = '';
  for (const item of items) {
    h += '<div class="eng-item"><span class="eng-val">' + formatNum(item.val) + '</span><span class="eng-label">' + item.label + '</span></div>';
  }
  if (engScore > 0) {
    h += '<div class="eng-item score"><span class="eng-val">' + engScore + '</span><span class="eng-label">互动分</span></div>';
  }
  el.innerHTML = h;
}

function addTagToVideo() {
  const v = Store.videos.find(x => x.id === Store.currentId);
  if (!v) return;
  const input = document.getElementById('detail-tag-input');
  if (!input) return;
  const tag = input.value.trim();
  if (!tag) return;
  if (!v.tags) v.tags = [];
  if (v.tags.includes(tag)) {
    // toast handled by import in app.js via window
    if (window.toast) window.toast('标签已存在', true);
    return;
  }
  v.tags.push(tag);
  input.value = '';
  renderDetailTags(v);
  API.post('/api/save', { id: Store.currentId, tags: v.tags }).catch(() => {});
  if (window.loadLibrary) window.loadLibrary();
}

function removeTagFromVideo(tag) {
  const v = Store.videos.find(x => x.id === Store.currentId);
  if (!v) return;
  v.tags = v.tags.filter(t => t !== tag);
  renderDetailTags(v);
  API.post('/api/save', { id: Store.currentId, tags: v.tags }).catch(() => {});
  if (window.loadLibrary) window.loadLibrary();
}

// ── Workflow Bar ──────────────────────────────
function buildWorkflowBar(v) {
  const st = v.transcript_status, ai = v.deepseek_status;
  const hasFile = !!v.file_size_mb;
  const steps = [
    { key: 'download', label: '下载', icon: '\u{1F4E5}', done: hasFile, active: false, disabled: !hasFile },
    { key: 'transcribe', label: '转写', icon: '\u{1F399}', done: st === 'done', active: hasFile && st !== 'done' && st !== 'error', disabled: !hasFile, error: st === 'error' },
    { key: 'analyze', label: 'AI分析', icon: '\u{1F9E0}', done: ai === 'done', active: st === 'done' && ai !== 'done' && ai !== 'error', disabled: st !== 'done', error: ai === 'error' },
  ];
  let h = '';
  for (const s of steps) {
    let cls = 'wf-step';
    if (s.done) cls += ' done';
    else if (s.active) cls += ' active';
    else if (s.disabled || s.error) cls += ' pending';
    if (s.error) cls += ' error';
    const click = s.active ? (' onclick="triggerWorkflowStep(\'' + s.key + '\')"') : '';
    const icon = s.done ? '\u2705' : s.error ? '\u274C' : s.icon;
    h += '<div class="' + cls + '"' + click + '><span class="wf-icon">' + icon + '</span>' + s.label + '</div>';
  }
  document.getElementById('detail-workflow').innerHTML = h;
}

// ── Action Bar ────────────────────────────────
function buildActionBar(v) {
  const st = v.transcript_status, ai = v.deepseek_status;
  let btns = '';
  if (st !== 'done') btns += '<button class="btn btn-primary btn-sm" onclick="triggerTranscribe()" id="btn-transcribe">\u{1F399} 开始转写</button>';
  if (st === 'done' && ai !== 'done') btns += '<button class="btn btn-primary btn-sm" onclick="triggerAI()">\u{1F9E0} AI 分析</button>';
  if (st === 'done') btns += '<button class="btn btn-ghost btn-sm" onclick="triggerReTranscribe()">\u{1F504} 重新转写</button>';
  if (ai === 'done') btns += '<button class="btn btn-ghost btn-sm" onclick="triggerReAnalyze()">\u{1F504} 重新分析</button>';
  if (st === 'error') btns += '<button class="btn btn-ghost btn-sm" onclick="triggerTranscribe()">\u{1F504} 重试转写</button>';
  btns += '<button class="btn btn-danger btn-sm" style="margin-left:auto" onclick="confirmDeleteVideo(\'' + v.id + '\',\'' + esc((v.title || v.id).substring(0, 40)) + '\')">\u{1F5D1} 删除</button>';
  document.getElementById('detail-actions').innerHTML = btns;
}

// ── Trigger workflow step ─────────────────────
function triggerWorkflowStep(key) {
  if (key === 'transcribe') triggerTranscribe();
  else if (key === 'analyze') triggerAI();
}

// ── Transcribe ────────────────────────────────
async function triggerTranscribe() {
  const id = Store.currentId;
  const v = Store.videos.find(x => x.id === id);
  if (!v) return;
  const btnTranscribe = document.getElementById('btn-transcribe');
  if (btnTranscribe) btnTranscribe.disabled = true;
  document.getElementById('detail-panel').innerHTML =
    '<div style="text-align:center;padding:40px 0"><span class="spinner" style="display:inline-block;width:18px;height:18px;border:2px solid var(--color-border);border-top-color:var(--color-accent);border-radius:50%;animation:spin .7s linear infinite"></span> <span style="color:var(--color-accent)">正在转写，请稍候...</span></div>';
  try {
    await API.post('/api/transcribe', { video_id: id });
    v.transcript_status = 'done';
    buildWorkflowBar(v);
    buildActionBar(v);
    switchDetailTab('transcript', document.querySelector('.detail-tab'));
    const t = await API.transcript(id);
    renderTranscript(t);
    if (window.loadLibrary) window.loadLibrary();
    if (window.toast) window.toast('转写完成', false);
  } catch (e) {
    document.getElementById('detail-panel').innerHTML =
      '<p style="color:var(--color-danger);text-align:center;line-height:1.8">转写失败<br><span style="font-size:.82rem">' + esc(e.message) +
      '</span><br><br><button class="btn btn-primary btn-sm" onclick="triggerTranscribe()">\u{1F504} 重试</button></p>';
    if (v) v.transcript_status = 'error';
    buildWorkflowBar(v);
    buildActionBar(v);
  }
}

// ── Re-transcribe ─────────────────────────────
async function triggerReTranscribe() {
  confirm('重新转写将覆盖现有转写数据，确定？', async () => {
    const id = Store.currentId;
    document.getElementById('detail-panel').innerHTML =
      '<div style="text-align:center;padding:40px 0"><span class="spinner" style="display:inline-block;width:18px;height:18px;border:2px solid var(--color-border);border-top-color:var(--color-accent);border-radius:50%;animation:spin .7s linear infinite"></span> <span style="color:var(--color-accent)">正在重新转写...</span></div>';
    try {
      await API.post('/api/transcribe', { video_id: id });
      const v = Store.videos.find(x => x.id === id);
      if (v) v.transcript_status = 'done';
      buildWorkflowBar(v);
      buildActionBar(v);
      switchDetailTab('transcript', document.querySelector('.detail-tab'));
      const t = await API.transcript(id);
      renderTranscript(t);
      if (window.loadLibrary) window.loadLibrary();
      if (window.toast) window.toast('重新转写完成', false);
    } catch (e) {
      document.getElementById('detail-panel').innerHTML =
        '<p style="color:var(--color-danger);text-align:center">重新转写失败: ' + esc(e.message) +
        '<br><br><button class="btn btn-primary btn-sm" onclick="triggerReTranscribe()">\u{1F504} 重试</button></p>';
    }
  });
}

// ── AI Analysis ───────────────────────────────
async function triggerAI() {
  const p = document.getElementById('detail-panel');
  const stages = ['🔍 正在读取转写内容...', '🧠 正在调用 DeepSeek 分析...', '📝 正在生成分析报告...'];
  let si = 0;
  const t0 = Date.now();
  const t = setInterval(() => {
    p.innerHTML =
      '<div style="text-align:center;padding:40px 0">' +
      '<div style="display:inline-flex;align-items:center;gap:10px;font-size:.9rem;color:var(--color-accent)">' +
      '<span class="spinner" style="display:inline-block;width:18px;height:18px;border:2px solid var(--color-border);border-top-color:var(--color-accent);border-radius:50%;animation:spin .7s linear infinite"></span>' +
      stages[si] + '</div>' +
      '<div style="font-size:.72rem;color:var(--color-text-dim);margin-top:8px">' + Math.floor((Date.now() - t0) / 1000) + 's</div>' +
      '</div>';
    si = (si + 1) % stages.length;
  }, 2200);
  try {
    await API.analyze({ video_id: Store.currentId });
    clearInterval(t);
    const v = Store.videos.find(x => x.id === Store.currentId);
    const r = await API.report(Store.currentId);
    p.innerHTML =
      '<div class="report">' + marked.parse(r) +
      '<div style="margin-top:16px;display:flex;gap:8px"><button class="btn btn-ghost btn-sm" onclick="copyReport()">\u{1F4CB} 复制报告</button><button class="btn btn-ghost btn-sm" onclick="downloadReport()">\u{1F4E5} 下载 .md</button></div></div>';
    if (v) { v.deepseek_status = 'done'; buildWorkflowBar(v); buildActionBar(v); }
    if (window.loadLibrary) window.loadLibrary();
    if (window.toast) window.toast('AI 分析完成 (耗时 ' + (Math.floor((Date.now() - t0) / 1000)) + 's)', false);
  } catch (e) {
    clearInterval(t);
    p.innerHTML =
      '<p style="color:var(--color-danger);text-align:center;line-height:1.8">AI 分析失败<br><span style="font-size:.82rem">' + esc(e.message) +
      '</span><br><br><button class="btn btn-primary btn-sm" onclick="triggerAI()">\u{1F504} 重试</button></p>';
    const v = Store.videos.find(x => x.id === Store.currentId);
    if (v) { v.deepseek_status = 'error'; buildWorkflowBar(v); buildActionBar(v); }
  }
}

// ── Re-analyze ────────────────────────────────
async function triggerReAnalyze() {
  confirm('重新分析将覆盖现有分析报告，确定？', async () => {
    await triggerAI();
  });
}

// ── Save inline title edit ────────────────────
async function saveTitle() {
  const input = document.getElementById('detail-title-input');
  if (!input) return;
  const newTitle = input.value.trim();
  if (!newTitle || !Store.currentId) return;
  const v = Store.videos.find(x => x.id === Store.currentId);
  if (v) v.title = newTitle;
  try {
    await API.post('/api/save', { id: Store.currentId, title: newTitle });
    if (window.toast) window.toast('标题已保存', false);
  } catch (e) {
    if (window.toast) window.toast('保存失败: ' + e.message, true);
  }
}

// ── Confirm Delete Video ──────────────────────
function confirmDeleteVideo(id, title) {
  confirm('确定要删除视频「' + title + '」吗？视频文件和分析数据将被永久删除。', async () => {
    try {
      await API.post('/api/delete', { id });
      Store.videos = Store.videos.filter(v => v.id !== id);
      if (Store.currentId === id) closeDetailModal();
      if (window.loadLibrary) await window.loadLibrary();
      if (window.toast) window.toast('已删除', false);
    } catch (e) {
      if (window.toast) window.toast('删除失败: ' + e.message, true);
    }
  });
}

// ── Open / Close Detail ───────────────────────
function closeDetailModal() {
  const v = document.getElementById('detail-video');
  v.pause();
  v.src = '';
  document.getElementById('detail-backdrop').classList.remove('open');
  Store.currentId = null;
}

async function openDetail(id) {
  Store.currentId = id;
  const v = Store.videos.find(x => x.id === id);
  if (!v) return;
  document.getElementById('detail-backdrop').classList.add('open');
  renderDetailTags(v);

  // Editable title
  document.getElementById('detail-title').innerHTML =
    '<input class="inline-edit" id="detail-title-input" value="' + esc(v.title || v.id || '') + '" onblur="saveTitle()" onkeydown="if(event.key===\'Enter\')this.blur()">';

  // Engagement metrics
  renderEngagementMetrics(v);

  const video = document.getElementById('detail-video');
  video.src = '/api/video-file/' + id;
  document.getElementById('detail-stage').style.display = 'block';
  video.onloadedmetadata = () => video.play().catch(() => {});

  buildWorkflowBar(v);
  buildActionBar(v);

  document.querySelectorAll('.detail-tab').forEach((b, i) => b.classList.toggle('active', i === 0));
  switchDetailTab('transcript', document.querySelector('.detail-tab'));
}

// ── Tab Switching ─────────────────────────────
async function switchDetailTab(tab, el) {
  document.querySelectorAll('.detail-tab').forEach(b => b.classList.remove('active'));
  if (el) el.classList.add('active');
  const p = document.getElementById('detail-panel');
  p.innerHTML =
    '<div style="text-align:center;padding:40px 0"><span class="spinner" style="display:inline-block;width:18px;height:18px;border:2px solid var(--color-border);border-top-color:var(--color-accent);border-radius:50%;animation:spin .7s linear infinite"></span></div>';
  if (tab === 'transcript') {
    try {
      renderTranscript(await API.transcript(Store.currentId));
    } catch {
      p.innerHTML = '<p style="color:var(--color-text-dim)">暂无转写数据。</p>';
    }
  } else if (tab === 'metrics') {
    try {
      renderMetrics(await API.analysis(Store.currentId));
    } catch {
      p.innerHTML = '<p style="color:var(--color-text-dim)">暂无指标数据。</p>';
    }
  } else if (tab === 'analysis') {
    try {
      const r = await API.report(Store.currentId);
      if (!r || !r.trim()) {
        p.innerHTML = '<p style="color:var(--color-text-dim);text-align:center;line-height:1.8">暂无 AI 分析报告。<br><br><button class="btn btn-primary btn-sm" onclick="triggerAI()">\u{1F9E0} 运行 AI 分析</button></p>';
        return;
      }
      p.innerHTML =
        '<div class="report">' + marked.parse(r) +
        '<div style="margin-top:16px;display:flex;gap:8px"><button class="btn btn-ghost btn-sm" onclick="copyReport()">\u{1F4CB} 复制报告</button><button class="btn btn-ghost btn-sm" onclick="downloadReport()">\u{1F4E5} 下载 .md</button></div></div>';
    } catch {
      p.innerHTML = '<p style="color:var(--color-text-dim)">暂无 AI 分析报告。</p>';
    }
  }
}

// ── Report copy / download ────────────────────
function copyReport() {
  const r = document.querySelector('.report');
  if (!r) return;
  navigator.clipboard.writeText(r.innerText).then(
    () => { if (window.toast) window.toast('已复制到剪贴板', false); },
    () => { if (window.toast) window.toast('复制失败', true); }
  );
}

function downloadReport() {
  const r = document.querySelector('.report');
  if (!r) return;
  const blob = new Blob([r.innerText], { type: 'text/markdown' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'report_' + Store.currentId + '.md';
  a.click();
  URL.revokeObjectURL(a.href);
  if (window.toast) window.toast('报告已下载', false);
}

// ── Transcript Rendering ──────────────────────
function renderTranscript(t) {
  const s = t.segments || [];
  if (!s.length) {
    document.getElementById('detail-panel').innerHTML = '<p style="color:var(--color-text-dim)">No transcript data.</p>';
    return;
  }
  let h = '';
  for (let i = 0; i < s.length; i++) {
    const m = Math.floor(s[i].start / 60), ss = Math.floor(s[i].start % 60);
    h += '<div class="transcript-seg" data-t="' + s[i].start + '" id="seg-' + i + '"><span class="seg-stamp" onclick="skipTo(' + s[i].start + ')">' + m + ':' + String(ss).padStart(2, '0') + '</span><span>' + esc(s[i].text) + '</span></div>';
  }
  document.getElementById('detail-panel').innerHTML = h;

  // Current-time syncing on video element
  document.getElementById('detail-video').ontimeupdate = function () {
    const ct = this.currentTime;
    const segs = document.querySelectorAll('.transcript-seg');
    const panel = document.getElementById('detail-panel');
    segs.forEach((s, i) => {
      const t = parseFloat(s.dataset.t);
      const n = segs[i + 1] ? parseFloat(segs[i + 1].dataset.t) : Infinity;
      if (ct >= t && ct < n) {
        if (!s.classList.contains('active')) {
          segs.forEach(x => x.classList.remove('active'));
          s.classList.add('active');
          panel.scrollTo({ top: s.offsetTop - panel.clientHeight / 3, behavior: 'smooth' });
        }
      }
    });
  };
}

// ── Skip to timestamp ─────────────────────────
function skipTo(t) {
  const v = document.getElementById('detail-video');
  v.currentTime = t;
  v.play();
}

// ── Metrics Rendering ─────────────────────────
function renderMetrics(a) {
  const p = document.getElementById('detail-panel');
  if (!a || !a.char_count) {
    p.innerHTML = '<p style="color:var(--color-text-dim)">No metrics available.</p>';
    return;
  }
  const cpm = a.chars_per_min || 0;
  const cpmC = cpm >= 295 && cpm <= 315 ? 'high' : cpm > 320 ? 'low' : 'mid';
  const kd = a.keyword_density || 0;
  const kdC = kd >= 2 && kd <= 3.5 ? 'high' : kd < 1.5 ? 'low' : 'mid';
  const em = a.emotion_keywords || 0;
  const emC = em >= 5 ? 'high' : em < 2 ? 'low' : 'mid';
  p.innerHTML =
    '<div class="stat-row"><span class="stat-label">Characters</span><span class="stat-val">' + (a.char_count || 0).toLocaleString() + '</span></div>' +
    '<div class="stat-row"><span class="stat-label">Duration</span><span class="stat-val">' + (a.duration || 0) + 's</span></div>' +
    '<div class="stat-row"><span class="stat-label">Speech rate</span><span class="stat-val ' + cpmC + '">' + cpm + ' cpm</span></div>' +
    '<div class="stat-row"><span class="stat-label">Segments</span><span class="stat-val">' + (a.segment_count || 0) + ' (avg ' + (a.avg_seg_chars || 0) + ')</span></div>' +
    '<div class="stat-row"><span class="stat-label">AI keywords</span><span class="stat-val">' + (a.ai_keywords || 0) + '</span></div>' +
    '<div class="stat-row"><span class="stat-label">Emotion words</span><span class="stat-val ' + emC + '">' + em + '</span></div>' +
    '<div class="stat-row"><span class="stat-label">Tech terms</span><span class="stat-val">' + (a.tech_keywords || 0) + '</span></div>' +
    '<div class="stat-row"><span class="stat-label">Keyword density</span><span class="stat-val ' + kdC + '">' + kd + '%</span></div>' +
    '<div style="margin-top:18px;padding:15px;background:var(--color-surface);border-radius:var(--radius-sm);border-left:3px solid var(--color-accent)"><div class="caption" style="margin-bottom:6px">Opening hook (first 30s)</div><div style="font-size:.84rem;color:var(--color-text-muted);line-height:1.6">' + (a.hook_text || '&mdash;') + '</div></div>' +
    '<div style="margin-top:10px;padding:15px;background:var(--color-surface);border-radius:var(--radius-sm);border-left:3px solid var(--color-text-dim)"><div class="caption" style="margin-bottom:6px">Closing (last 30s)</div><div style="font-size:.84rem;color:var(--color-text-dim);line-height:1.6">' + (a.close_text || '&mdash;') + '</div></div>';
}

export const VideoDetail = {
  openDetail,
  closeDetailModal,
  switchDetailTab,
  renderTranscript,
  renderMetrics,
  skipTo,
  triggerAI,
  triggerReAnalyze,
  triggerTranscribe,
  triggerReTranscribe,
  triggerWorkflowStep,
  buildWorkflowBar,
  buildActionBar,
  saveTitle,
  copyReport,
  downloadReport,
  renderDetailTags,
  addTagToVideo,
  removeTagFromVideo,
  confirmDeleteVideo,
  calcEngagementScore,
};
