// ═══════════════════════════════════════
// Pipeline Progress — progress bar + stepper + polling
// ═══════════════════════════════════════

import { API } from '../api.js';

export async function runOnePipeline(url, mode, procEntry, renderGridFn, showErrorFn) {
  const tempId = 'task_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6);
  let progressTimer = null;

  const pollProgress = async () => {
    try {
      const p = await API.get('/api/progress?video_id=' + tempId);
      if (p && p.percent !== undefined && procEntry) {
        const step = p.step || 'download';
        const status = p.status || '';
        const stepLabel = step === 'transcribe' ? '转写' : step === 'analyze' ? '分析' : step === 'download' ? '下载' : step;
        if (status === 'analyzing') {
          procEntry._status = 'AI 分析中...';
          procEntry._pct = 50;
        } else {
          procEntry._status = stepLabel + ' ' + p.percent + '%';
          procEntry._pct = p.percent;
        }
        renderGridFn();
      }
    } catch {}
  };
  progressTimer = setInterval(pollProgress, 800);
  pollProgress();

  try {
    const r = await API.process({ url, mode, video_id: tempId });
    if (progressTimer) clearInterval(progressTimer);
    const steps = r.steps || [];
    if (steps.some(s => s.status === 'error')) {
      if (procEntry) { procEntry._status = '部分失败'; procEntry._pct = 0; renderGridFn(); }
      showErrorFn('部分步骤执行失败', steps);
      throw new Error('Pipeline step error');
    }
    if (procEntry) { procEntry._status = '处理完成'; procEntry._pct = 100; renderGridFn(); }
  } catch (e) {
    if (progressTimer) clearInterval(progressTimer);
    if (procEntry) { procEntry._status = '处理失败'; procEntry._pct = 0; renderGridFn(); }
    let steps = [];
    try { const errBody = JSON.parse(e.message); steps = errBody.steps || []; } catch {}
    showErrorFn(e.message, steps);
  }
}

export const Pipeline = { runOnePipeline };
