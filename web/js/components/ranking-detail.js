// ═══════════════════════════════════════
// Ranking Detail — 右列视频详情面板
// ═══════════════════════════════════════

import { Store } from '../store.js';
import { API } from '../api.js';
import { esc } from '../utils.js';

function render(video) {
  const container = document.getElementById('ranking-detail-panel');
  if (!container) return;

  if (!video) {
    container.innerHTML = '<div class="rk-detail-placeholder"><div class="rk-detail-placeholder-icon">&#128269;</div><div>点击左侧视频查看详情</div></div>';
    return;
  }

  let durText = '未知';
  if (video.duration_sec > 0) {
    const m = Math.floor(video.duration_sec / 60);
    const s = video.duration_sec % 60;
    durText = m > 0 ? m + '分' + s + '秒' : s + '秒';
  }

  let h = '<div class="rk-detail-inner">';
  // 视频预览
  h += '<div class="rk-detail-preview">';
  if (video.cover_url) {
    h += '<img src="' + video.cover_url + '" class="rk-detail-cover" onerror="this.style.display=\'none\'">';
  } else {
    h += '<div class="rk-detail-cover-no">&#9654;</div>';
  }
  h += '</div>';

  // 基本信息
  h += '<div class="rk-detail-info">';
  h += '<h3 class="rk-detail-title">' + esc(video.title || '') + '</h3>';
  h += '<div class="rk-detail-row"><span class="rk-detail-label">作者</span><span>' + esc(video.author || '未知') + '</span></div>';
  h += '<div class="rk-detail-row"><span class="rk-detail-label">时长</span><span>' + durText + '</span></div>';
  h += '<div class="rk-detail-row"><span class="rk-detail-label">播放量</span><span>' + formatPlay(video.play_count) + '</span></div>';
  h += '</div>';

  // 标签
  if (video.tags && video.tags.length > 0) {
    h += '<div class="rk-detail-tags">';
    for (const t of video.tags) {
      h += '<span class="rk-detail-tag">#' + esc(t) + '</span>';
    }
    h += '</div>';
  }

  // 操作按钮
  h += '<div class="rk-detail-actions">';
  if (video.share_url) {
    h += '<a class="btn btn-ghost btn-sm" href="' + video.share_url + '" target="_blank">查看原链接</a>';
  }
  h += '<button class="btn btn-primary btn-sm" onclick="downloadRankingVideo(\'' + video.id + '\',\'' + video.platform + '\')">下载并分析</button>';
  h += '</div>';

  h += '</div>';
  container.innerHTML = h;
}

function formatPlay(n) {
  if (!n) return '0';
  if (n >= 1e8) return (n / 1e8).toFixed(1) + ' 亿';
  if (n >= 1e4) return (n / 1e4).toFixed(0) + ' 万';
  return n.toLocaleString();
}

export const RankingDetail = { render };
