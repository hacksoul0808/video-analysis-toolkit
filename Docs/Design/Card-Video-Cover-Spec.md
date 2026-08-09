# Card Video Cover — Requirement Spec

**Date**: 2026-08-10
**Decision**: B — Pure frontend `<video>` preview, hover-triggered first 5s loop
**Related Files**: `analyzer.html` (CSS/JS), no server changes required

---

## 1. Overview

Replace the static ◆ placeholder in video card media areas with embedded `<video>` elements that play a muted, 5-second loop on mouse hover. No server-side changes — the existing `/api/video-file/{video_id}` endpoint already supports Range-based streaming.

---

## 2. Functional Requirements

### 2.1 Card Media States

| State | Condition | Display |
|-------|-----------|---------|
| **Processing** | `v._processing === true` | Keep existing shimmer + loader-ring (no change) |
| **No Video** | `v.id` has no MP4 in `library/videos/{id}/` | Show ◆ placeholder (fallback, same as current) |
| **Normal** | MP4 exists, not processing | Show `<video>` poster frame, hover to play |

### 2.2 Video Element Spec

```html
<video
  src="/api/video-file/{video_id}"
  muted
  loop
  playsinline
  preload="none"
  disableRemotePlayback
  class="card-video"
></video>
```

- `muted` — required for browser autoplay policy
- `playsinline` — required for iOS Safari
- `preload="none"` — avoid loading all card videos on page load (performance)
- `disableRemotePlayback` — prevent AirPlay/Cast prompts

### 2.3 Hover Behavior

- **mouseenter** (or touchstart on mobile):
  1. Set `video.preload = "auto"`
  2. `video.currentTime = 0`
  3. `video.play()` (returns Promise, catch and ignore rejection)
  4. Register `timeupdate` listener: when `currentTime >= 5`, seek back to 0
- **mouseleave**:
  1. `video.pause()`
  2. Keep the last frame as poster (browser default behavior)

### 2.4 5-Second Loop Logic

```javascript
function handleCardHover(video) {
  video.preload = 'auto';
  video.currentTime = 0;
  video.play().catch(() => {});
  
  const onTimeUpdate = () => {
    if (video.currentTime >= 5) {
      video.currentTime = 0;
    }
  };
  video.addEventListener('timeupdate', onTimeUpdate);
  video._timeUpdateHandler = onTimeUpdate;
}

function handleCardLeave(video) {
  video.pause();
  if (video._timeUpdateHandler) {
    video.removeEventListener('timeupdate', video._timeUpdateHandler);
    video._timeUpdateHandler = null;
  }
  video.preload = 'none';
}
```

### 2.5 Event Delegation

Since `renderGrid()` uses `innerHTML`, video event listeners must be attached via:
- **Option 1 (recommended)**: Add `onmouseenter` / `onmouseleave` inline attributes directly in the HTML string during `renderGrid()`.
- **Option 2**: Use event delegation on `#video-grid` with `data-video-id` attribute.

**Recommend Option 1** (inline attributes) — simpler, no DOM querying after render.

Inline attribute approach:
```javascript
h += '<video class="card-video" src="/api/video-file/' + v.id + '" muted loop playsinline preload="none" disableRemotePlayback onmouseenter="previewPlay(this)" onmouseleave="previewStop(this)"></video>';
```

Add two global helper functions:
- `previewPlay(video)` — implements the hover logic above
- `previewStop(video)` — implements the leave logic above

---

## 3. CSS Changes

### 3.1 Card Media Container

Current `.card-media` already has `aspect-ratio: 16/9`, `overflow: hidden`, `position: relative`. This works for `<video>` with minimal changes.

### 3.2 Video Element Styles

```css
.card-video {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  background: var(--color-bg);
}
```

### 3.3 Placeholder Fallback

Keep `.card-media-symbol` for cards without video files:
```css
.card-media-symbol {
  font-size: 2.4rem;
  opacity: .15;
  font-family: var(--font-display);
  color: var(--color-accent);
}
```

### 3.4 Overlay Elements (duration, score)

`.card-dur` and `.card-score` are `position: absolute` on `.card-media`. They must appear **above** the video:
```css
.card-dur, .card-score {
  z-index: 2;
}
```

### 3.5 Hover Glow Effect

The existing `.card-media::after` radial gradient overlay should remain as a visual polish layer above the video but below text overlays:
```css
.card-media::after {
  z-index: 1;
}
```

---

## 4. Performance Strategy

| Concern | Mitigation |
|---------|-----------|
| Too many `<video>` elements on page | `preload="none"` — no network requests until hover |
| Hover triggers full download | Only 5 seconds worth of data downloaded (~1-2MB) due to Range requests and pause |
| Memory accumulation | On leave, reset `preload="none"` and pause |
| Scroll performance | Videos outside viewport are `preload="none"`, no impact |

---

## 5. Edge Cases

| Case | Handling |
|------|----------|
| Browser blocks autoplay | `play().catch(() => {})` — silent fallback, stays on poster frame |
| iOS Safari | `playsinline` attribute prevents fullscreen takeover |
| Card clicked to open detail | Detail modal already has separate `<video>` player — no conflict |
| Processing card | Keep shimmer/loader-ring, no video element |
| `renderGrid()` called while video playing | `innerHTML` re-render destroys old element — old video stops. New element loads fresh. Acceptable. |
| Card added to library before download completes (e.g., batch pipeline) | `download_status !== 'done'` → show ◆ placeholder |

---

## 6. File Check Strategy

Need a way to know whether a video file exists from the frontend. Options:

- **Option A**: Add a `has_video` boolean field to `library.json` entries (set during pipeline save)
- **Option B**: Pre-check with HEAD request to `/api/video-file/{id}` — but this adds latency
- **Option C (recommended)**: Check `transcript_status === 'done'` — if transcript exists, MP4 exists (transcript requires downloaded video)

**Recommend Option C** for simplicity, with fallback: if `<video>` errors (404), hide and show ◆ placeholder.

Add `onerror` handler:
```html
<video ... onerror="this.style.display='none';this.nextElementSibling.style.display='block'">
<span class="card-media-symbol" style="display:none">&#9670;</span>
```

---

## 7. Implementation Checklist

- [ ] Add CSS: `.card-video` styles, z-index layers for overlays
- [ ] Add CSS: hover transition effect (optional: slight scale or glow)
- [ ] Add JS: `previewPlay(video)` and `previewStop(video)` global functions
- [ ] Modify `renderGrid()`: replace `card-media-symbol` with `<video>` + hidden fallback for normal cards
- [ ] Modify `renderGrid()`: keep processing card logic unchanged
- [ ] Add JS: video existence check (`v.transcript_status === 'done'` or `v.download_status === 'done'`)
- [ ] Test: hover triggers 5s loop
- [ ] Test: leave stops and resets
- [ ] Test: multiple cards, no memory leak
- [ ] Test: mobile touch behavior

---

## 8. Handoff

Requirements confirmed. Please @system-architect-guardian review the technical approach, or @vibe-maker proceed with frontend implementation based on this spec.
