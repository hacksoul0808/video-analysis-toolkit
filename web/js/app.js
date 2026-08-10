// ═══════════════════════════════════════
// App Entry — init, switchView, global event listeners, DOM ready
// ═══════════════════════════════════════

import { API } from './api.js';
import { Store } from './store.js';
import { toast, playSound, unlockAudio } from './components/toast.js';
import { confirm, closeConfirm } from './components/confirm-modal.js';
import { VideoCard } from './components/video-card.js';
import { VideoDetail } from './components/video-detail.js';
import { AddModal } from './components/add-modal.js';
import { Pipeline } from './components/pipeline.js';
import { TagManager } from './components/tag-manager.js';
import { LibraryView } from './views/library.js';
import { MethodologyView } from './views/methodology.js';
import { StatsView } from './views/stats.js';

// ═══════════════════════════════════════
// View Switching
// ═══════════════════════════════════════
function switchView(v) {
  Store.view = v;
  document.querySelectorAll('.app-bar-nav button').forEach((b, i) =>
    b.classList.toggle('active', ['library', 'methodology', 'stats'].indexOf(v) === i)
  );
  document.getElementById('view-library').style.display = v === 'library' ? 'block' : 'none';
  document.getElementById('view-methodology').style.display = v === 'methodology' ? 'block' : 'none';
  document.getElementById('view-stats').style.display = v === 'stats' ? 'block' : 'none';
  if (v === 'library') LibraryView.loadLibrary();
  if (v === 'methodology') MethodologyView.loadMeta();
  if (v === 'stats') StatsView.loadStats();
}

// ═══════════════════════════════════════
// Expose to window for inline HTML handlers
// ═══════════════════════════════════════
Object.assign(window, {
  // App
  switchView,
  Store,
  API,

  // Toast / Sound
  toast, playSound, unlockAudio,

  // Confirm (legacy name for inline handlers)
  showConfirm: confirm,
  closeConfirmModal: closeConfirm,

  // VideoCard
  previewPlay: VideoCard.previewPlay,
  previewStop: VideoCard.previewStop,

  // Pipeline
  Pipeline,

  // Video Detail
  openDetail: VideoDetail.openDetail,
  closeDetailModal: VideoDetail.closeDetailModal,
  switchDetailTab: VideoDetail.switchDetailTab,
  triggerWorkflowStep: VideoDetail.triggerWorkflowStep,
  triggerTranscribe: VideoDetail.triggerTranscribe,
  triggerReTranscribe: VideoDetail.triggerReTranscribe,
  triggerAI: VideoDetail.triggerAI,
  triggerReAnalyze: VideoDetail.triggerReAnalyze,
  confirmDeleteVideo: VideoDetail.confirmDeleteVideo,
  copyReport: VideoDetail.copyReport,
  downloadReport: VideoDetail.downloadReport,
  skipTo: VideoDetail.skipTo,
  saveTitle: VideoDetail.saveTitle,
  addTagToVideo: VideoDetail.addTagToVideo,
  removeTagFromVideo: VideoDetail.removeTagFromVideo,

  // Add Modal
  openAddModal: AddModal.openAddModal,
  closeAddModal: AddModal.closeAddModal,
  switchAddMode: AddModal.switchAddMode,
  updateBatchCount: AddModal.updateBatchCount,
  loadImportList: AddModal.loadImportList,
  importVideo: AddModal.importVideo,
  startPipeline: AddModal.startPipeline,
  setMode: AddModal.setMode,
  closeErrorModal: AddModal.closeErrorModal,
  showErrorModal: AddModal.showErrorModal,

  // Tag Manager
  openTagModal: TagManager.openTagModal,
  closeTagModal: TagManager.closeTagModal,
  refreshTagList: TagManager.refreshTagList,
  renameTagPrompt: TagManager.renameTagPrompt,
  deleteTagPrompt: TagManager.deleteTagPrompt,

  // Library View
  loadLibrary: LibraryView.loadLibrary,
  filterTag: LibraryView.filterTag,
  sortBy: LibraryView.sortBy,
  onSearchInput: LibraryView.onSearchInput,
  clearSearch: LibraryView.clearSearch,
  batchAnalyze: LibraryView.batchAnalyze,
  clearSelection: LibraryView.clearSelection,
  toggleSelectMode: LibraryView.toggleSelectMode,

  // Methodology
  loadMeta: MethodologyView.loadMeta,

  // Stats
  loadStats: StatsView.loadStats,

  // Bridge for add-modal pipeline rendering
  renderGridFn: LibraryView.renderGridWrapper,
});

// ═══════════════════════════════════════
// Global Event Listeners
// ═══════════════════════════════════════

// Modal backdrop click-to-close
document.getElementById('add-backdrop').addEventListener('click', function (e) {
  if (e.target === this && !Store.locked) AddModal.closeAddModal();
});
document.getElementById('detail-backdrop').addEventListener('click', function (e) {
  if (e.target === this) VideoDetail.closeDetailModal();
});
document.getElementById('error-backdrop').addEventListener('click', function (e) {
  if (e.target === this) AddModal.closeErrorModal();
});
document.getElementById('confirm-backdrop').addEventListener('click', function (e) {
  if (e.target === this) closeConfirm();
});
document.getElementById('tag-backdrop').addEventListener('click', function (e) {
  if (e.target === this) TagManager.closeTagModal();
});

// Multi-select: intercept card clicks in select mode (capture phase)
document.addEventListener('click', function (e) {
  if (!Store.selectMode) return;
  const card = e.target.closest('.video-card');
  if (!card || card.classList.contains('processing')) return;
  if (e.target.closest('.card-del')) return;
  e.stopPropagation();
  e.preventDefault();
  const m = card.getAttribute('onclick')?.match(/openDetail\('([^']+)'\)/);
  if (m) LibraryView.toggleCardSelect(m[1]);
}, true);

// ═══════════════════════════════════════
// Init
// ═══════════════════════════════════════
function init() {
  LibraryView.initSelectMode();
  LibraryView.loadLibrary();
}

// Run on DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

export const App = { init, switchView };
