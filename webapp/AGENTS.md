# AGENTS.md — WebApp / Telegram Mini App (TMA) & PWA Client

Guide for AI agents modifying, extending, or testing files in `webapp/`.

---

## 🏛️ Architecture & Overview

The `webapp/` directory contains the modern, responsive web application for **Kalich Reborn**, operating in two modes:
1. **Telegram Mini App (TMA)**: Loaded inside Telegram client using the Telegram WebApp SDK (`telegram-web-app.js`).
2. **Standalone Web & PWA**: Accessible via standard web browsers with full offline capabilities via Service Worker (`sw.js`) and Web Manifest (`manifest.json`).

---

## 📁 Key Files & Invariants

- **`index.html`**:
  - Single-page application markup.
  - Contains PWA metadata, Apple Mobile Web App tags, viewport-fit cover, and font imports.
  - Section tabs:
    - `#tab-schedule`: Main dashboard (Now widget, today's schedule, tomorrow's schedule, weekday pills).
    - `#tab-teachers`: Classrooms and teacher schedule search with quick room chips.
    - `#tab-bells`: Bell schedule list and `.ics` calendar sync download/copy.
    - `#tab-settings`: User profile, manual theme toggle, and Kalich Lore "About" card.
- **`app.js`**:
  - `LESSON_CALLS`: Slot-to-time map for 10 college lessons (0..9).
  - `buildLessonBlocks(lessons)`: Groups consecutive identical subjects into cards with duration in minutes and combined lesson numbers (`1–4 УРОКИ`).
  - `updateLiveBellsTimer()`: Real-time `/now` widget driver with progress bar, active lesson badge, remaining time countdown, and break reminders.
  - `applyTheme(theme)`: Switches themes (`tg`, `dark`, `light`) and persists selection in `localStorage`.
  - Service Worker registration on load.
- **`styles.css`**:
  - CSS custom properties (`--bg-color`, `--text-color`, `--card-bg`, etc.).
  - Supports `[data-theme="dark"]`, `[data-theme="light"]`, and default/Telegram colors.
  - Responsive cards, badges, pulse animations, and mobile safe-area insets.
- **`sw.js`**:
  - Offline Service Worker caching static assets (Cache-First) and `/api/` endpoints (Network-First with offline fallback).
- **`manifest.json`**:
  - PWA manifest configuration (`standalone`, portrait orientation, icons).
- **`icons/`**:
  - Adaptive 192x192 and 512x512 PWA icons.

---

## 🔌 API Serving (`api_server.py`)

Static routes in `api_server.py`:
- `/` & `/index.html` → `webapp/index.html`
- `/styles.css` → `webapp/styles.css`
- `/app.js` → `webapp/app.js`
- `/manifest.json` → `webapp/manifest.json`
- `/sw.js` → `webapp/sw.js`
- `/icons/*` → `webapp/icons/*`

`_find_pwa_file()` in `api_server.py` searches `webapp/` first before falling back to legacy paths.
