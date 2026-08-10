// ═══════════════════════════════════════
// Video Card — rendering, hover preview, event binding
// ═══════════════════════════════════════

import { esc, formatTime } from '../utils.js';
import { VideoDetail } from './video-detail.js';

// ── Card Video Preview ────────────────────────
export function previewPlay(video) {
  video.preload = 'auto';
  video.currentTime = 0;
  video.play().catch(() => {});
  const onTimeUpdate = () => { if (video.currentTime >= 5) video.currentTime = 0; };
  video.addEventListener('timeupdate', onTimeUpdate);
  video._timeUpdateHandler = onTimeUpdate;
}

export function previewStop(video) {
  video.pause();
  if (video._timeUpdateHandler) {
    video.removeEventListener('timeupdate', video._timeUpdateHandler);
    video._timeUpdateHandler = null;
  }
}

// ── Skeleton Loading ──────────────────────────
export function renderSkeletons() {
  let h = '';
  for (let i = 0; i < 6; i++) {
    h += '<div class="skeleton-card"><div class="skeleton-media"></div><div class="skeleton-body"><div class="skeleton-line mid"></div><div class="skeleton-line short"></div></div></div>';
  }
  document.getElementById('video-grid').innerHTML = h;
}

// ── Load Error State ──────────────────────────
export function renderLoadError(id, msg, retryFn) {
  const el = document.getElementById(id);
  el.innerHTML =
    '<div class="error-state"><span class="err-icon">&#9888;</span>' +
    '<div class="err-msg">' + esc(msg) + '</div>' +
    '<button class="btn btn-primary btn-sm" id="retry-btn-' + id + '">&#x1F504; 重试</button></div>';
  if (retryFn) {
    el.querySelector('#retry-btn-' + id).addEventListener('click', retryFn);
  }
}

// ── Render Video Grid ─────────────────────────
// videos: array of video objects
// selectMode: whether multi-select is active
// selected: object of selected video ids
export function renderGrid(videos, selectMode, selected) {
  const g = document.getElementById('video-grid');
  if (!videos.length) {
    g.innerHTML = '<div class="empty-state"><span class="empty-state-icon">&#9670;</span><h3>暂无视频</h3><p>添加视频链接，自动分析文案并提取爆款方法论。</p><button class="btn btn-primary" onclick="openAddModal()">添加视频</button></div>';
    return;
  }
  let h = '';
  for (const v of videos) {
    if (v._processing) {
      const pct = v._pct || 0;
      h += '<div class="video-card processing">';
      h += '<div class="card-media-processing"><div class="loader-ring"></div>';
      h += '<div class="card-shimmer"></div>';
      h += '<span class="proc-step-badge">' + v._status + '</span>';
      h += '</div><div class="card-body">';
      h += '<h3>' + esc(v.url) + '</h3>';
      h += '<div style="height:3px;background:var(--color-border);border-radius:2px;margin:8px 0;overflow:hidden">';
      h += '<div style="height:100%;width:' + pct + '%;background:var(--color-accent);border-radius:2px;transition:width .3s ease"></div></div>';
      h += '<div class="card-footer"><div class="card-status" style="color:var(--color-accent)">' + pct + '%</div><span class="card-date">处理中</span></div>';
      h += '</div></div>';
      continue;
    }
    const sc = VideoDetail.calcEngagementScore(v.metrics);
    const st = v.transcript_status === 'done';
    const ai = v.deepseek_status === 'done';
    const dur = v.duration_sec ? formatTime(v.duration_sec) : '--';
    const dt = (v.created_at || '').slice(0, 10);
    const tier = sc >= 60 ? 'hot' : sc >= 40 ? 'good' : 'ok';
    h += '<div class="video-card" data-tier="' + tier + '" onclick="openDetail(\'' + v.id + '\')">';
    h += '<button class="card-del" onclick="event.stopPropagation();confirmDeleteVideo(\'' + v.id + '\',\'' + esc((v.title || v.id).substring(0, 40)) + '\')" title="删除">\u00D7</button>';
    h += '<div class="card-media">';
    if (st || v.download_status === 'done') {
      const poster = (v.has_cover && v.cover_file) ? ' poster="/api/video/cover/' + v.id + '"' : '';
      h += '<video class="card-video" src="/api/video-file/' + v.id + '"' + poster + ' muted loop playsinline preload="none" disableRemotePlayback onmouseenter="previewPlay(this)" onmouseleave="previewStop(this)" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'"></video>';
      h += '<span class="card-media-symbol" style="display:none">&#9670;</span>';
    } else {
      h += '<span class="card-media-symbol">&#9670;</span>';
    }
    h += '<span class="card-dur">' + dur + '</span>';
    if (sc > 0) h += '<span class="card-score ' + tier + '">' + sc + '</span>';
    h += '</div><div class="card-body">';
    h += '<h3>' + esc(v.title || v.id) + '</h3>';
    h += '<div class="card-tags">' + (v.tags || []).slice(0, 3).map(t => '<span class="card-tag">' + t + '</span>').join('') + '</div>';
    h += '<div class="card-footer"><div class="card-status">';
    h += '<span class="' + (st ? 'ok' : '') + '">转写 ' + (st ? '&check;' : '&mdash;') + '</span>';
    h += '<span class="' + (ai ? 'ok' : '') + '">分析 ' + (ai ? '&check;' : '&mdash;') + '</span>';
    h += '</div><span class="card-date">' + dt + '</span></div>';
    h += '</div></div>';
  }
  g.innerHTML = h;

  // Multi-select mode: add checkboxes and select-mode classes
  if (selectMode) {
    g.querySelectorAll('.video-card').forEach(c => c.classList.add('select-mode'));
    g.querySelectorAll('.video-card:not(.processing)').forEach(c => {
      const m = c.getAttribute('onclick')?.match(/openDetail\('([^']+)'\)/);
      if (!m) return;
      if (c.querySelector('.card-checkbox')) return;
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.className = 'card-checkbox';
      cb.checked = !!selected[m[1]];
      c.insertBefore(cb, c.firstChild);
    });
  }
}

export const VideoCard = { renderGrid, renderSkeletons, previewPlay, previewStop, renderLoadError };
