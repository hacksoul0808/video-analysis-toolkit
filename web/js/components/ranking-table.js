// ═══════════════════════════════════════
// Ranking Table — 左列排行表格
// ═══════════════════════════════════════

import { Store } from '../store.js';
import { API } from '../api.js';
import { esc } from '../utils.js';

let _onSelectDetail = null;

function onSelectDetail(fn) { _onSelectDetail = fn; }

// ── 格式化播放量 ──
function fmtPlay(n) {
  if (n >= 1e8) return (n / 1e8).toFixed(1) + '亿';
  if (n >= 1e4) return (n / 1e4).toFixed(0) + '万';
  return String(n);
}

// ── 排名颜色 ──
function rankColor(idx) {
  if (idx === 0) return '#FFD700';
  if (idx === 1) return '#C0C0C0';
  if (idx === 2) return '#CD7F32';
  return 'var(--color-text-dim)';
}

// ── 渲染表格 ──
function render() {
  const container = document.getElementById('ranking-table-body');
  const pageInfo = document.getElementById('ranking-page-info');
  if (!container) return;

  const r = Store.ranking;
  const data = r.data;
  const total = data.length;
  const start = (r.currentPage - 1) * r.pageSize;
  const end = Math.min(start + r.pageSize, total);
  const pageData = data.slice(start, end);
  const totalPages = Math.max(1, Math.ceil(total / r.pageSize));

  if (total === 0) {
    container.innerHTML = '<div class="ranking-empty">暂无排行数据</div>';
    if (pageInfo) pageInfo.textContent = '第 0/0 页';
    return;
  }

  let h = '';
  for (let i = 0; i < pageData.length; i++) {
    const v = pageData[i];
    const globalIdx = start + i;
    const sel = r.selectedIds.has(v.id) ? ' selected' : '';
    const activeCls = r.selectedDetail && r.selectedDetail.id === v.id ? ' active-row' : '';
    const rc = rankColor(globalIdx);
    const dur = v.duration_sec > 0 ? v.duration_sec + 's' : '--';
    const escTitle = esc(v.title || '');

    h += '<div class="ranking-row' + sel + activeCls + '" data-id="' + v.id + '">';
    h += '<div class="rk-col-check"><input type="checkbox" class="rk-checkbox" ' + (sel ? 'checked' : '') + ' onchange="toggleRankingSelect(\'' + v.id + '\',this)" onclick="event.stopPropagation()"></div>';
    h += '<div class="rk-col-rank" style="color:' + rc + '">' + (globalIdx + 1) + '</div>';
    h += '<div class="rk-col-cover">';
    if (v.cover_url) h += '<img src="' + v.cover_url + '" class="rk-cover-img" loading="lazy" onerror="this.style.display=\'none\'">';
    h += '</div>';
    h += '<div class="rk-col-title"><span class="rk-title-text" onclick="selectRankingDetail(\'' + v.id + '\')">' + escTitle + '</span></div>';
    h += '<div class="rk-col-dur">' + dur + '</div>';
    h += '<div class="rk-col-play">' + fmtPlay(v.play_count) + '</div>';
    h += '</div>';
  }
  container.innerHTML = h;

  if (pageInfo) pageInfo.textContent = '第 ' + r.currentPage + '/' + totalPages + ' 页（共 ' + total + ' 条）';
  updateToolbar();
}

// ── 翻页 ──
function prevPage() {
  const r = Store.ranking;
  if (r.currentPage > 1) {
    r.currentPage--;
    render();
  }
}

function nextPage() {
  const r = Store.ranking;
  const totalPages = Math.max(1, Math.ceil(r.data.length / r.pageSize));
  if (r.currentPage < totalPages) {
    r.currentPage++;
    render();
  }
}

// ── 全选 ──
function toggleSelectAll() {
  const r = Store.ranking;
  const start = (r.currentPage - 1) * r.pageSize;
  const end = Math.min(start + r.pageSize, r.data.length);
  const pageData = r.data.slice(start, end);
  const allSelected = pageData.every(v => r.selectedIds.has(v.id));
  if (allSelected) {
    for (const v of pageData) r.selectedIds.delete(v.id);
  } else {
    for (const v of pageData) r.selectedIds.add(v.id);
  }
  render();
}

function toggleSelect(id, checkbox) {
  const r = Store.ranking;
  if (checkbox.checked) {
    r.selectedIds.add(id);
  } else {
    r.selectedIds.delete(id);
  }
  updateToolbar();
}

// ── 选中详情 ──
function selectDetail(id) {
  const r = Store.ranking;
  if (r.selectedDetail && r.selectedDetail.id === id) return;
  const v = r.data.find(x => x.id === id);
  if (!v) return;
  r.selectedDetail = v;
  render();
  if (_onSelectDetail) _onSelectDetail(v);
}

// ── 工具栏 ──
function updateToolbar() {
  const r = Store.ranking;
  const count = r.selectedIds.size;
  const btn = document.getElementById('ranking-batch-dl-btn');
  const lbl = document.getElementById('ranking-select-count');
  if (lbl) lbl.textContent = '已选 ' + count + ' 个';
  if (btn) btn.disabled = count === 0;
}

// ── 渲染骨架屏 ──
function renderSkeletons() {
  const container = document.getElementById('ranking-table-body');
  if (!container) return;
  let h = '';
  for (let i = 0; i < 8; i++) {
    h += '<div class="ranking-row skeleton"><div class="rk-col-check"></div><div class="rk-col-rank"></div><div class="rk-col-cover"><div class="skeleton-box"></div></div><div class="rk-col-title"><div class="skeleton-line"></div></div><div class="rk-col-dur"><div class="skeleton-line"></div></div><div class="rk-col-play"><div class="skeleton-line"></div></div></div>';
  }
  container.innerHTML = h;
}

function renderError(msg, retryFn) {
  const container = document.getElementById('ranking-table-body');
  if (!container) return;
  container.innerHTML = '<div class="ranking-error"><div class="ranking-error-msg">' + esc(msg) + '</div><button class="btn btn-primary btn-sm" onclick="(' + retryFn.toString() + ')()">重试</button></div>';
}

function renderInfo(msg) {
  const container = document.getElementById('ranking-table-body');
  if (!container) return;
  container.innerHTML = '<div class="ranking-empty" style="padding:40px 20px;text-align:center;color:var(--color-text-muted)">' + esc(msg) + '</div>';
}

export const RankingTable = {
  render, renderSkeletons, renderError, renderInfo,
  prevPage, nextPage, toggleSelectAll, toggleSelect, selectDetail,
  updateToolbar, onSelectDetail,
};
