// ═══════════════════════════════════════
// Confirm Dialog
// ═══════════════════════════════════════

let _confirmCb = null;

export function confirm(msg, cb) {
  document.getElementById('confirm-msg').textContent = msg;
  document.getElementById('confirm-backdrop').classList.add('open');
  _confirmCb = cb;
  document.getElementById('confirm-ok-btn').onclick = () => {
    const cb = _confirmCb;
    closeConfirm();
    if (cb) cb();
  };
}

export function closeConfirm() {
  document.getElementById('confirm-backdrop').classList.remove('open');
  _confirmCb = null;
}
