// ═══════════════════════════════════════
// Methodology View
// ═══════════════════════════════════════

import { API } from '../api.js';
import { esc } from '../utils.js';

async function loadMeta() {
  const c = document.getElementById('meta-content');
  c.innerHTML = '<div style="text-align:center;padding:60px 0"><span class="spinner" style="display:inline-block;width:20px;height:20px;border:3px solid var(--color-border);border-top-color:var(--color-accent);border-radius:50%;animation:spin .7s linear infinite"></span></div>';
  try {
    const d = await API.methodology(window.Store ? window.Store.tag : null);
    if (!d.total_analyzed) {
      c.innerHTML = '<div class="empty-state"><span class="empty-state-icon">&#9670;</span><h3>暂无数据</h3><p>完成至少一个视频的 AI 分析后，这里会展示方法论文本。</p></div>';
      return;
    }
    let h = '<div class="meta-grid">';
    h += '<div class="meta-card"><h3>开场钩子分布</h3><div class="hook-row">';
    for (const [n, k] of (d.hook_patterns || [])) h += '<span class="hook-badge">' + esc(n) + ' (' + k + ')</span>';
    if (!d.hook_patterns.length) h += '<span style="color:var(--color-text-dim);font-size:.84rem">暂无钩子数据</span>';
    h += '</div></div>';

    h += '<div class="meta-card"><h3>可复用标题模板</h3>';
    for (const t of (d.title_templates || []).slice(0, 6)) h += '<div class="tpl-item">' + esc(t) + '</div>';
    if (!d.title_templates.length) h += '<span style="color:var(--color-text-dim);font-size:.84rem">暂无模板</span>';
    h += '</div>';

    h += '<div class="meta-card"><h3>高分案例 (score &ge; 75)</h3>';
    for (const e of (d.best_examples || [])) h += '<div class="example-row" onclick="openDetail(\'' + e.id + '\')"><span>' + esc((e.title || '').substring(0, 55)) + '</span><span class="card-score hot" style="position:static;display:inline-flex">' + e.viral_score + '</span></div>';
    if (!d.best_examples.length) h += '<span style="color:var(--color-text-dim);font-size:.84rem">暂无高分案例</span>';
    h += '</div></div>';

    c.innerHTML = h;
  } catch (e) {
    c.innerHTML = '<div class="error-state"><span class="err-icon">&#9888;</span><div class="err-msg">加载方法论失败<br>' + esc(e.message) + '</div><button class="btn btn-primary btn-sm" onclick="loadMeta()">\u{1F504} 重试</button></div>';
  }
}

export const MethodologyView = { loadMeta };
