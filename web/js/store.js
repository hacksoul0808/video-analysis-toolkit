// ═══════════════════════════════════════
// Global State
// ═══════════════════════════════════════

export const Store = {
  view: 'library',
  tag: null,
  sort: 'created_at',
  searchQuery: '',
  videos: [],
  tags: [],
  currentId: null,
  mode: 'full',
  locked: false,
  selectMode: false,
  selected: {},
  addMode: 'single',

  // 排行榜状态
  ranking: {
    platform: 'douyin',
    data: [],
    currentPage: 1,
    pageSize: 50,
    selectedIds: new Set(),
    selectedDetail: null,
    isStale: false,
    batchDownloading: false,
    batchProgress: null
  }
};
