// ═══════════════════════════════════════
// Batch Download Bar — 批量下载进度条
// ═══════════════════════════════════════

import { Store } from '../store.js';
import { API } from '../api.js';

let _pollTimer = null;

function show() {
  const bar = document.getElementById('batch-dl-bar');
  if (bar) bar.classList.add('show');
  Store.ranking.batchDownloading = true;
}

function hide() {
  const bar = document.getElementById('batch-dl-bar');
  if (bar) bar.classList.remove('show');
  Store.ranking.batchDownloading = false;
  Store.ranking.batchProgress = null;
  if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
}

async function startPolling() {
  show();
  const platform = Store.ranking.platform;

  const poll = async () => {
    try {
      const p = await API.get('/api/ranking/batch-progress?platform=' + platform);
      Store.ranking.batchProgress = p;
      render(p);

      if (p.finished) {
        hide();
        if (window.toast) {
          const total = p.total || 0;
          const failed = p.failed || 0;
          window.toast(total + ' 个视频已加入下载队列' + (failed ? '（' + failed + ' 个失败）' : '') + '，可在视频库查看');
        }
      }
    } catch (e) {
      hide();
      if (window.toast) window.toast('批量下载进度获取失败: ' + e.message, true);
    }
  };

  _pollTimer = setInterval(poll, 2000);
  poll(); // 立即执行一次
}

function render(p) {
  const bar = document.getElementById('batch-dl-bar');
  if (!bar) return;
  const total = p.total || 0;
  const completed = p.completed || 0;
  const failed = p.failed || 0;
  const downloading = p.downloading || 0;
  const finished = p.finished;

  const pct = total > 0 ? Math.round(((completed + failed) / total) * 100) : 0;
  let statusText = '';
  if (finished) {
    statusText = '下载完成: ' + (completed + failed) + '/' + total;
  } else if (downloading) {
    statusText = '下载中: ' + (completed + failed) + '/' + total;
  } else {
    statusText = '排队中: ' + total + ' 个视频';
  }

  bar.innerHTML =
    '<div class="batch-dl-bar-inner">' +
    '<span class="batch-dl-status">' + statusText + '</span>' +
    '<div class="batch-dl-progress">' +
    '<div class="batch-dl-fill" style="width:' + pct + '%"></div>' +
    '</div>' +
    '<span class="batch-dl-pct">' + pct + '%</span>' +
    (finished ? '<button class="batch-dl-close" onclick="hideBatchDownloadBar()">&times;</button>' : '') +
    '</div>';
}

export const BatchDownloadBar = { show, hide, startPolling, render };
