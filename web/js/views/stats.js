// ═══════════════════════════════════════
// Stats View — KPI cards + Chart.js charts
// ═══════════════════════════════════════

import { API } from '../api.js';
import { VideoCard } from '../components/video-card.js';

let liveCharts = [];

async function loadStats() {
  document.getElementById('kpi-strip').innerHTML =
    '<div style="text-align:center;padding:40px 0"><span class="spinner" style="display:inline-block;width:20px;height:20px;border:3px solid var(--color-border);border-top-color:var(--color-accent);border-radius:50%;animation:spin .7s linear infinite"></span></div>';
  document.getElementById('chart-row').innerHTML = '';
  try {
    const d = await API.stats();
    document.getElementById('kpi-strip').innerHTML =
      '<div class="kpi-tile"><div class="num accent">' + (d.total_videos || 0) + '</div><div class="lbl">视频总数</div></div>' +
      '<div class="kpi-tile"><div class="num">' + (d.avg_viral_score || 0) + '</div><div class="lbl">平均爆款分</div></div>' +
      '<div class="kpi-tile"><div class="num warn">' + (d.score_distribution ? d.score_distribution['爆款(60+)'] || 0 : 0) + '</div><div class="lbl">爆款 (60+)</div></div>' +
      '<div class="kpi-tile"><div class="num">' + (d.score_distribution ? d.score_distribution['优质(40-59)'] || 0 : 0) + '</div><div class="lbl">优质 (40-59)</div></div>';
    renderCharts(d);
  } catch (e) {
    document.getElementById('kpi-strip').innerHTML = '';
    VideoCard.renderLoadError('chart-row', '加载统计数据失败:<br>' + e.message, () => loadStats());
  }
}

function renderCharts(d) {
  liveCharts.forEach(c => c.destroy());
  liveCharts = [];
  const row = document.getElementById('chart-row');
  if (!d.total_videos) {
    row.innerHTML = '<div class="empty-state"><p>No data to chart.</p></div>';
    return;
  }
  let h = '';
  if (d.score_distribution) h += '<div class="chart-box"><h4>Score distribution</h4><canvas id="ch-score"></canvas></div>';
  if (d.by_tag && Object.keys(d.by_tag).length) h += '<div class="chart-box"><h4>Tags by avg score</h4><canvas id="ch-tags"></canvas></div>';
  row.innerHTML = h || '<div class="empty-state"><p>Not enough data.</p></div>';

  Chart.defaults.color = '#64748b';
  Chart.defaults.borderColor = '#1e2a34';

  if (d.score_distribution) {
    const sd = d.score_distribution;
    const ctx = document.getElementById('ch-score');
    if (ctx) {
      liveCharts.push(new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels: Object.keys(sd),
          datasets: [{ data: Object.values(sd), backgroundColor: ['#2dd4bf', '#fbbf24', '#64748b', '#334155'] }]
        },
        options: { responsive: true, plugins: { legend: { position: 'bottom', labels: { padding: 16 } } } }
      }));
    }
  }

  if (d.by_tag && Object.keys(d.by_tag).length) {
    const e = Object.entries(d.by_tag).sort((a, b) => b[1].count - a[1].count).slice(0, 8);
    const ctx = document.getElementById('ch-tags');
    if (ctx) {
      liveCharts.push(new Chart(ctx, {
        type: 'bar',
        data: {
          labels: e.map(x => x[0]),
          datasets: [
            { label: 'Count', data: e.map(x => x[1].count), backgroundColor: 'rgba(45,212,191,.25)', borderColor: '#2dd4bf', borderWidth: 1, yAxisID: 'y' },
            { label: 'Avg score', data: e.map(x => x[1].avg_score), type: 'line', borderColor: '#fbbf24', yAxisID: 'y1', tension: .3 }
          ]
        },
        options: {
          responsive: true,
          scales: { y: { position: 'left', grid: { color: '#1e2a34' } }, y1: { position: 'right', grid: { display: false }, min: 0, max: 100 } },
          plugins: { legend: { labels: { padding: 16 } } }
        }
      }));
    }
  }
}

export const StatsView = { loadStats, renderCharts };
