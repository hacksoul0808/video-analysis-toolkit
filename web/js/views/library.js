// ═══════════════════════════════════════
// Video Library View — render grid, tag filter, sort, search, multi-select, batch
// ═══════════════════════════════════════

import { API } from '../api.js';
import { Store } from '../store.js';
import { VideoCard } from '../components/video-card.js';
import { esc } from '../utils.js';

let searchTimer = null;

// ── Load Library ──────────────────────────────
async function loadLibrary() {
  const grid = document.getElementById('video-grid');
  if (!Store.videos.length) VideoCard.renderSkeletons();
  try {
    const d = await API.library(Store.tag, Store.sort, Store.searchQuery);
    Store.videos = d.videos || [];
    Store.tags = d.tags || [];
    document.getElementById('lib-heading').textContent = Store.tag ? '筛选: ' + Store.tag : '视频库';
    renderTags();
    renderGridWrapper();
  } catch (e) {
    VideoCard.renderLoadError('video-grid', '加载视频库失败:<br>' + e.message, () => loadLibrary());
  }
}

// ── Render Tags ───────────────────────────────
function renderTags() {
  const c = document.getElementById('tag-cloud');
  let h = '<button class="tag-chip' + (!Store.tag ? ' active' : '') + '" onclick="filterTag(null)">全部 (' + Store.videos.length + ')</button>';
  for (const [n, k] of Store.tags.slice(0, 14)) {
    h += '<button class="tag-chip' + (Store.tag === n ? ' active' : '') + '" onclick="filterTag(\'' + n + '\')">' + n + ' (' + k + ')</button>';
  }
  h += '<button class="tag-chip" style="border:1px dashed var(--color-border);color:var(--color-text-dim);opacity:.7" onclick="openTagModal()">+ 管理标签</button>';
  c.innerHTML = h;
}

// ── Filter / Sort ─────────────────────────────
function filterTag(t) {
  Store.tag = t;
  loadLibrary();
}

function sortBy(s, el) {
  Store.sort = s;
  document.querySelectorAll('#sort-row .btn-ghost').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  loadLibrary();
}

// ── Search ────────────────────────────────────
function onSearchInput() {
  const q = document.getElementById('search-input').value.trim();
  document.getElementById('search-clear').classList.toggle('show', q.length > 0);
  Store.searchQuery = q;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadLibrary(), 300);
}

function clearSearch() {
  document.getElementById('search-input').value = '';
  document.getElementById('search-clear').classList.remove('show');
  Store.searchQuery = '';
  loadLibrary();
}

// ── Render Grid Wrapper (with multi-select) ───
function renderGridWrapper() {
  VideoCard.renderGrid(Store.videos, Store.selectMode, Store.selected);
  updateSelectUI();
}

// ── Multi-Select ──────────────────────────────
function toggleSelectMode() {
  Store.selectMode = !Store.selectMode;
  Store.selected = {};
  document.getElementById('multi-bar').classList.toggle('show', Store.selectMode);
  document.querySelectorAll('.video-card').forEach(c => c.classList.toggle('select-mode', Store.selectMode));
  updateSelectUI();
}

function toggleCardSelect(id) {
  if (!Store.selectMode) return window.openDetail ? window.openDetail(id) : null;
  if (Store.selected[id]) delete Store.selected[id];
  else Store.selected[id] = true;
  document.querySelectorAll('.video-card').forEach(c => {
    const m = c.getAttribute('onclick')?.match(/openDetail\('([^']+)'\)/)?.[1];
    if (m) c.classList.toggle('selected', !!Store.selected[m]);
  });
  updateSelectUI();
}

function updateSelectUI() {
  const count = Object.keys(Store.selected).length;
  document.getElementById('select-count').textContent = '已选 ' + count + ' 个';
  document.getElementById('batch-analyze-btn').disabled = count === 0;
}

function clearSelection() {
  Store.selectMode = false;
  Store.selected = {};
  document.getElementById('multi-bar').classList.remove('show');
  document.querySelectorAll('.video-card').forEach(c => { c.classList.remove('select-mode', 'selected'); });
  renderGridWrapper();
}

async function batchAnalyze() {
  const ids = Object.keys(Store.selected);
  if (!ids.length) {
    if (window.toast) window.toast('请选择至少一个视频', true);
    return;
  }
  clearSelection();
  Store.videos.filter(v => ids.includes(v.id) && v.transcript_status === 'done').forEach(v => { v.deepseek_status = 'running'; });
  renderGridWrapper();
  let done = 0, err = 0;
  for (const id of ids) {
    const v = Store.videos.find(x => x.id === id);
    if (!v || v.transcript_status !== 'done') continue;
    try {
      await API.analyze({ video_id: id });
      v.deepseek_status = 'done';
      done++;
    } catch (e) {
      v.deepseek_status = 'error';
      err++;
    }
    renderGridWrapper();
  }
  loadLibrary();
  if (window.toast) window.toast('批量分析完成: ' + done + ' 成功' + (err ? ', ' + err + ' 失败' : ''));
}

// ── Init: add multi-select toggle button ──────
function initSelectMode() {
  const sortRow = document.getElementById('sort-row');
  if (!sortRow) return;
  const btn = document.createElement('button');
  btn.className = 'btn btn-ghost btn-sm';
  btn.style.marginLeft = 'auto';
  btn.textContent = '多选模式';
  btn.onclick = toggleSelectMode;
  sortRow.appendChild(btn);
}

export const LibraryView = {
  loadLibrary, renderTags, filterTag, sortBy,
  onSearchInput, clearSearch,
  toggleSelectMode, toggleCardSelect, updateSelectUI, clearSelection, batchAnalyze,
  initSelectMode, renderGridWrapper,
};
