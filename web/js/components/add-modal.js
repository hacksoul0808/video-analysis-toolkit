// ═══════════════════════════════════════
// Add Video Modal — mode switch, URL input, pipeline trigger
// ═══════════════════════════════════════

import { API } from '../api.js';
import { Store } from '../store.js';
import { runOnePipeline } from './pipeline.js';
import { esc } from '../utils.js';

// ── Open / Close ──────────────────────────────
function openAddModal() {
  if (window.unlockAudio) window.unlockAudio();
  Store.locked = false;
  Store.mode = 'full';
  document.getElementById('add-backdrop').classList.add('open');
  document.getElementById('add-url').value = '';
  document.getElementById('add-url').focus();
  document.getElementById('pipeline-area').style.display = 'none';
  document.getElementById('pipeline-done').innerHTML = '';
  document.getElementById('start-btn').style.display = '';
}

function closeAddModal() {
  if (!Store.locked) document.getElementById('add-backdrop').classList.remove('open');
}

// ── Add Mode Switch ───────────────────────────
function switchAddMode(mode, el) {
  Store.addMode = mode;
  document.querySelectorAll('#add-mode-toggle .btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('single-url-field').style.display = mode === 'single' ? 'block' : 'none';
  document.getElementById('batch-url-field').style.display = mode === 'batch' ? 'block' : 'none';
  document.getElementById('import-field').style.display = mode === 'import' ? 'block' : 'none';
  const startBtn = document.getElementById('start-btn');
  if (mode === 'import') {
    startBtn.style.display = 'none';
    loadImportList();
  } else {
    startBtn.style.display = '';
  }
  if (mode === 'single') { document.getElementById('add-url').focus(); }
  else if (mode === 'batch') { document.getElementById('batch-urls').focus(); updateBatchCount(); }
}

// ── Batch count ───────────────────────────────
function updateBatchCount() {
  const lines = document.getElementById('batch-urls').value.split('\n').filter(l => l.trim());
  document.getElementById('batch-url-count').textContent = lines.length + ' 个链接';
}

// ── Import List ───────────────────────────────
async function loadImportList() {
  const c = document.getElementById('import-list');
  c.innerHTML = '<div style="text-align:center;padding:30px 0"><span class="spinner" style="display:inline-block;width:16px;height:16px;border:2px solid var(--color-border);border-top-color:var(--color-accent);border-radius:50%;animation:spin .7s linear infinite"></span></div>';
  try {
    const d = await API.get('/api/scan-videos');
    const vids = d.videos || [];
    if (!vids.length) {
      c.innerHTML = '<p style="color:var(--color-text-dim);text-align:center;padding:20px">没有可导入的视频<br><span style="font-size:.78rem">将 mp4 放入 videos/ 目录后刷新</span></p>';
      return;
    }
    let h = '';
    for (const v of vids) {
      h += '<div style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border-bottom:1px solid var(--color-border);cursor:pointer;transition:background .15s" onmouseover="this.style.background=\'var(--color-accent-dim)\'" onmouseout="this.style.background=\'transparent\'" onclick="importVideo(\'' + esc(v.filepath) + '\',\'' + esc(v.title) + '\')">';
      h += '<span style="font-size:.82rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;margin-right:10px">' + esc(v.title || v.filename) + '</span>';
      h += '<span style="font-size:.76rem;color:var(--color-text-dim);white-space:nowrap">' + v.size_mb + ' MB</span>';
      h += '</div>';
    }
    c.innerHTML = h;
  } catch (e) {
    c.innerHTML = '<div class="error-state" style="padding:20px"><span class="err-icon" style="font-size:1.2rem">&#9888;</span><div class="err-msg" style="font-size:.8rem">' + esc(e.message) + '</div><button class="btn btn-primary btn-sm" onclick="loadImportList()">重试</button></div>';
  }
}

// ── Import Video ──────────────────────────────
async function importVideo(filepath, title) {
  try {
    await API.post('/api/import', { filepath, title });
    if (window.toast) window.toast('已导入: ' + title, false);
    loadImportList();
    if (window.loadLibrary) window.loadLibrary();
    closeAddModal();
  } catch (e) {
    if (window.toast) window.toast('导入失败: ' + e.message, true);
  }
}

// ── Set Mode ──────────────────────────────────
function setMode(m, el) {
  Store.mode = m;
  document.querySelectorAll('.radio-option').forEach(r => r.classList.remove('selected'));
  el.classList.add('selected');
}

// ── Error Modal ───────────────────────────────
function showErrorModal(msg, steps) {
  const names = { download: '下载视频', transcribe: '语音转写', script_analysis: '指标分析', ai_analysis: 'AI 分析' };
  const list = document.getElementById('error-step-list');
  const detail = document.getElementById('error-detail');

  if (steps && steps.length > 0) {
    let h = '<div style="display:flex;flex-direction:column;gap:6px">';
    for (const s of steps) {
      const ok = s.status === 'done';
      h += '<div class="err-step ' + (ok ? 'ok' : 'fail') + '">';
      h += '<span class="dot">' + (ok ? '\u2714' : '\u2716') + '</span>';
      h += '<span class="step-name">' + (names[s.step] || s.step) + '</span>';
      h += '<span class="step-tag">' + (ok ? '完成' : '失败') + '</span></div>';
    }
    h += '</div>';
    list.innerHTML = h;
    const firstErr = steps.find(s => s.status === 'error');
    if (firstErr && firstErr.error) {
      detail.style.display = 'block';
      detail.innerHTML = '<div style="font-weight:600;color:var(--color-danger);margin-bottom:6px">错误详情</div>' + esc(firstErr.error);
    } else {
      detail.style.display = 'none';
    }
  } else {
    list.innerHTML = '<div style="font-size:.85rem;color:var(--color-text-dim)">' + esc(msg) + '</div>';
    detail.style.display = 'none';
  }
  document.getElementById('error-backdrop').classList.add('open');
}

function closeErrorModal() {
  document.getElementById('error-backdrop').classList.remove('open');
}

// ── Pipeline Entry ────────────────────────────
// Helper: get renderGrid function from window (set by app.js)
function _renderGrid() {
  if (window.renderGridFn) window.renderGridFn();
}

function _showError(msg, steps) {
  showErrorModal(msg, steps);
}

async function startPipeline() {
  if (Store.addMode === 'single') {
    await startSinglePipeline();
  } else {
    await startBatchPipeline();
  }
}

async function startSinglePipeline() {
  const url = document.getElementById('add-url').value.trim();
  if (!url) {
    if (window.toast) window.toast('请输入视频链接', true);
    return;
  }

  document.getElementById('add-backdrop').classList.remove('open');

  const procEntry = { _processing: true, url: url, _status: '准备下载...', _mode: Store.mode, _pct: 0 };
  Store.videos.unshift(procEntry);
  _renderGrid();

  await runOnePipeline(url, Store.mode, procEntry, _renderGrid, _showError);

  Store.videos = Store.videos.filter(v => !v._processing);
  if (window.loadLibrary) await window.loadLibrary();
  if (window.playSound) window.playSound('success');
  if (window.toast) window.toast('分析完成！', false);
}

async function startBatchPipeline() {
  const urls = document.getElementById('batch-urls').value.split('\n').map(l => l.trim()).filter(l => l);
  if (!urls.length) {
    if (window.toast) window.toast('请输入至少一个视频链接', true);
    return;
  }
  const mode = Store.mode;
  document.getElementById('add-backdrop').classList.remove('open');

  for (let i = 0; i < urls.length; i++) {
    const url = urls[i];
    const procEntry = { _processing: true, url: url, _status: '排队中 (' + (i + 1) + '/' + urls.length + ')', _mode: mode, _pct: 0 };
    Store.videos.unshift(procEntry);
    _renderGrid();
    try {
      await runOnePipeline(url, mode, procEntry, _renderGrid, _showError);
      procEntry._status = '处理完成';
      procEntry._pct = 100;
      _renderGrid();
    } catch (e) {
      procEntry._status = '处理失败';
      procEntry._pct = 0;
      _renderGrid();
    }
  }
  Store.videos = Store.videos.filter(v => !v._processing);
  if (window.loadLibrary) await window.loadLibrary();
  if (window.playSound) window.playSound('success');
  if (window.toast) window.toast('批量处理完成！共 ' + urls.length + ' 个视频', false);
}

export const AddModal = {
  openAddModal, closeAddModal, switchAddMode, updateBatchCount,
  loadImportList, importVideo, startPipeline, startSinglePipeline, startBatchPipeline,
  setMode, showErrorModal, closeErrorModal,
};
