// ═══════════════════════════════════════
// Utility Functions
// ═══════════════════════════════════════

export function esc(s) {
  if (!s) return '';
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

export function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return m + ':' + String(s).padStart(2, '0');
}

export function debounce(fn, delay) {
  let timer = null;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

/**
 * 从抖音/快手等平台的分享文本中提取视频链接。
 * 如果输入已是纯 URL 则原样返回；否则匹配文本中的第一个链接，优先 douyin.com。
 * @param {string} text - 用户粘贴的原始文本
 * @returns {string} 提取出的链接，若未找到则返回原文本
 */
export function extractUrl(text) {
  if (!text) return '';

  const trimmed = text.trim();

  // 输入就是纯链接，直接返回
  if (/^https?:\/\/\S+$/i.test(trimmed)) return trimmed;

  // 查找所有 URL
  const urlPattern = /https?:\/\/[^\s\u4e00-\u9fff]+/gi;
  const matches = trimmed.match(urlPattern);
  if (!matches || matches.length === 0) return trimmed;

  // 优先抖音链接
  const douyinMatch = matches.find(u => /douyin\.com/i.test(u));
  if (douyinMatch) return douyinMatch.replace(/[,，。.!！?？;；、）\)】\]》〉"'"…]+$/, '');

  // 返回第一个匹配到的 URL
  return matches[0];
}
