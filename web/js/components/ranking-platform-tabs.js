// ═══════════════════════════════════════
// Ranking Platform Tabs — 平台切换子 Tab
// ═══════════════════════════════════════

import { Store } from '../store.js';

const PLATFORMS = [
  { id: 'douyin', label: '抖音', active: true },
  { id: 'tiktok', label: 'TikTok', active: true },
  { id: 'kuaishou', label: '快手', active: false },
  { id: 'xiaohongshu', label: '小红书', active: false },
  { id: 'youtube', label: 'YouTube', active: false },
  { id: 'bilibili', label: 'B站', active: false }
];

let _onSwitch = null; // 外部注册的平台切换回调

function render() {
  const container = document.getElementById('ranking-platform-tabs');
  if (!container) return;
  const r = Store.ranking;
  let h = '';
  for (const p of PLATFORMS) {
    const sel = r.platform === p.id ? ' active' : '';
    const cls = p.active ? '' : ' disabled';
    h += '<button class="platform-tab-btn' + sel + cls + '" data-platform="' + p.id + '" onclick="switchRankingPlatform(\'' + p.id + '\')">' + p.label + '</button>';
  }
  container.innerHTML = h;
}

function switchPlatform(id) {
  const p = PLATFORMS.find(x => x.id === id);
  if (!p) return;
  if (!p.active) {
    if (window.toast) window.toast(p.label + ' 即将上线');
    return;
  }
  if (Store.ranking.platform === id) return;
  Store.ranking.platform = id;
  Store.ranking.data = [];
  Store.ranking.currentPage = 1;
  Store.ranking.selectedIds = new Set();
  Store.ranking.selectedDetail = null;
  render();
  if (_onSwitch) _onSwitch(id);
}

function onSwitch(fn) {
  _onSwitch = fn;
}

export const RankingTabs = { render, switchPlatform, onSwitch };
export { PLATFORMS };
