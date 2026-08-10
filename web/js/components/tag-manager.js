// ═══════════════════════════════════════
// Tag Management — rename / delete / merge
// ═══════════════════════════════════════

import { API } from '../api.js';
import { confirm } from './confirm-modal.js';
import { esc } from '../utils.js';

// ── Open / Close ──────────────────────────────
async function openTagModal() {
  document.getElementById('tag-backdrop').classList.add('open');
  await refreshTagList();
}

function closeTagModal() {
  document.getElementById('tag-backdrop').classList.remove('open');
}

// ── Refresh Tag List ──────────────────────────
async function refreshTagList() {
  const c = document.getElementById('tag-list-content');
  c.innerHTML = '<div style="text-align:center;padding:30px 0"><span class="spinner" style="display:inline-block;width:16px;height:16px;border:2px solid var(--color-border);border-top-color:var(--color-accent);border-radius:50%;animation:spin .7s linear infinite"></span></div>';
  try {
    const tags = await API.get('/api/tags');
    const items = tags.tags || [];
    if (!items.length) {
      c.innerHTML = '<p style="color:var(--color-text-dim);text-align:center;padding:20px">暂无标签</p>';
      return;
    }
    let h = '';
    for (const [name, count] of items) {
      h += '<div class="tag-manage-row" style="display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--color-border)">';
      h += '<span style="font-size:.84rem"><span class="card-tag" style="padding:4px 10px">' + esc(name) + '</span> <span style="color:var(--color-text-dim);font-size:.78rem">(' + count + ' 个视频)</span></span>';
      h += '<span style="display:flex;gap:4px">';
      h += '<button class="btn btn-ghost btn-xs" onclick="renameTagPrompt(\'' + esc(name) + '\')" title="重命名">\u270F</button>';
      h += '<button class="btn btn-ghost btn-xs" onclick="deleteTagPrompt(\'' + esc(name) + '\',\'' + count + '\')" title="删除" style="color:var(--color-danger)">\u2716</button>';
      h += '</span></div>';
    }
    c.innerHTML = h;
  } catch (e) {
    c.innerHTML = '<div class="error-state"><span class="err-icon">&#9888;</span><div class="err-msg">' + esc(e.message) + '</div><button class="btn btn-primary btn-sm" onclick="refreshTagList()">重试</button></div>';
  }
}

// ── Rename Tag ────────────────────────────────
function renameTagPrompt(oldName) {
  const n = prompt('将「' + oldName + '」重命名为：', oldName);
  if (!n || n.trim() === oldName || !n.trim()) return;
  renameTag(oldName, n.trim());
}

async function renameTag(oldName, newName) {
  try {
    await API.post('/api/tags', { action: 'rename', tag: oldName, new_tag: newName });
    if (window.toast) window.toast('已重命名: ' + oldName + ' → ' + newName, false);
    refreshTagList();
    if (window.loadLibrary) window.loadLibrary();
  } catch (e) {
    if (window.toast) window.toast('重命名失败: ' + e.message, true);
  }
}

// ── Delete Tag ────────────────────────────────
function deleteTagPrompt(name, count) {
  confirm('删除标签「' + name + '」将从所有 ' + count + ' 个视频中移除此标签。确定？', async () => {
    try {
      await API.post('/api/tags', { action: 'delete', tag: name });
      if (window.toast) window.toast('已删除标签: ' + name, false);
      refreshTagList();
      if (window.loadLibrary) window.loadLibrary();
    } catch (e) {
      if (window.toast) window.toast('删除失败: ' + e.message, true);
    }
  });
}

export const TagManager = {
  openTagModal, closeTagModal, refreshTagList,
  renameTagPrompt, renameTag, deleteTagPrompt,
};
