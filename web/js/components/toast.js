// ═══════════════════════════════════════
// Toast Notification
// ═══════════════════════════════════════

let _audioUnlocked = false;

export function unlockAudio() {
  if (_audioUnlocked) return;
  _audioUnlocked = true;
  const a = new Audio();
  a.volume = 0;
  a.play().then(() => { a.pause(); a.currentTime = 0; }).catch(() => {});
}

export function playSound(name) {
  unlockAudio();
  try {
    const a = new Audio('/sounds/' + name + '.mp3');
    a.volume = 0.6;
    a.play().catch(() => {});
  } catch {}
}

export function toast(m, err) {
  const t = document.createElement('div');
  t.className = 'toast' + (err ? ' err' : '');
  t.textContent = m;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3600);
}
