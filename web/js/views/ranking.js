// ═══════════════════════════════════════
// Ranking View — 排行榜视图控制器
// ═══════════════════════════════════════

import { API } from '../api.js';
import { Store } from '../store.js';
import { RankingTabs, PLATFORMS } from '../components/ranking-platform-tabs.js';
import { RankingTable } from '../components/ranking-table.js';
import { RankingDetail } from '../components/ranking-detail.js';
import { BatchDownloadBar } from '../components/batch-download-bar.js';

let _pollBatchTimer = null;

// ── 加载排行数据 ──
async function loadRanking() {
  const r = Store.ranking;
  RankingTable.renderSkeletons();
  RankingDetail.render(null);
  const isStaleEl = document.getElementById('ranking-stale-hint');
  if (isStaleEl) isStaleEl.style.display = 'none';

  try {
    const data = await API.get('/api/ranking/' + r.platform + '?page=1&page_size=100');
    r.data = data.videos || [];
    r.isStale = data.is_stale || false;
    r.currentPage = 1;
    r.selectedIds = new Set();
    r.selectedDetail = null;

    if (data.error && r.data.length === 0) {
      RankingTable.renderInfo('该平台排行暂不可用: ' + data.error + '<br><button class="btn btn-ghost btn-sm" onclick="retryLoadRanking()" style="margin-top:12px">刷新排行</button>');
    } else {
      RankingTable.render();
      if (r.isStale && isStaleEl) {
        isStaleEl.style.display = 'block';
      }
    }
  } catch (e) {
    RankingTable.renderError('加载排行失败: ' + e.message, () => loadRanking());
  }
}

// ── 平台切换 ──
async function onPlatformSwitch(platform) {
  RankingTabs.render();
  await loadRanking();
}

// ── 选中视频详情 ──
function onSelectDetail(video) {
  RankingDetail.render(video);
}

// ── 单个下载 ──
async function downloadSingle(videoId, platform) {
  const data = await API.post('/api/ranking/batch-download', {
    platform: platform,
    video_ids: [videoId],
    auto_analyze: false,
  });
  const queued = data.queued_count || 0;
  const skipped = data.skipped_count || 0;
  if (queued > 0) {
    BatchDownloadBar.startPolling();
  } else if (skipped > 0) {
    if (window.toast) window.toast('该视频已在视频库中');
  }
}

// ── 批量下载 ──
async function batchDownload() {
  const r = Store.ranking;
  const selectedIds = [...r.selectedIds];
  if (selectedIds.length === 0) {
    if (window.toast) window.toast('请先勾选要下载的视频');
    return;
  }

  if (window.showConfirm) {
    window.showConfirm('将下载 ' + selectedIds.length + ' 个视频到视频库，确定？', async () => {
      await executeBatchDownload(selectedIds);
    });
  } else {
    await executeBatchDownload(selectedIds);
  }
}

async function executeBatchDownload(selectedIds) {
  const r = Store.ranking;
  const data = await API.post('/api/ranking/batch-download', {
    platform: r.platform,
    video_ids: selectedIds,
    auto_analyze: false,
  });
  const queued = data.queued_count || 0;
  const skipped = data.skipped_count || 0;
  let msg = queued + ' 个视频已加入下载队列';
  if (skipped > 0) msg += '，' + skipped + ' 个已在库中已跳过';
  if (window.toast) window.toast(msg);
  r.selectedIds = new Set();
  RankingTable.render();
  if (queued > 0) BatchDownloadBar.startPolling();
}

// ── 刷新排行 ──
async function refreshRanking() {
  const r = Store.ranking;
  const btn = document.getElementById('ranking-refresh-btn');
  if (btn) { btn.disabled = true; btn.textContent = '刷新中...'; }
  try {
    await API.post('/api/ranking/' + r.platform + '/refresh', {});
    r.data = [];
    await loadRanking();
    if (window.toast) window.toast('排行数据已刷新');
  } catch (e) {
    if (window.toast) window.toast('刷新失败: ' + e.message, true);
  }
  if (btn) { btn.disabled = false; btn.textContent = '刷新排行'; }
}

// ── 视图初始化 ──
function init() {
  RankingTabs.onSwitch(onPlatformSwitch);
  RankingTable.onSelectDetail(onSelectDetail);
  RankingTabs.render();
  loadRanking();
}

// ── 视图销毁（切换到其他 Tab 时调用）──
function cleanup() {
  if (_pollBatchTimer) { clearInterval(_pollBatchTimer); _pollBatchTimer = null; }
}

export const RankingView = { init, loadRanking, batchDownload, refreshRanking, downloadSingle, onSelectDetail, cleanup };
