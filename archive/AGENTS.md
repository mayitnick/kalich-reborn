# AGENTS.md — Information Regarding Archived Assets

This directory contains archived components that have been decommissioned or frozen.

---

## 📦 Archived Artifacts

- `archive/pwa/` and `archive/pwa.tar.gz`:
  - The Progressive Web App (PWA) client originally intended as a WebApp interface for Telegram.
  - Frozen and archived per user instruction.
  - `Dockerfile.frontend` and Docker Compose frontend service are disabled.

---

## 🚫 Rules for AI Agents

1. **Do not modify or rebuild archived code**:
   - Unless explicitly requested by the user, do not add features, run builds, or re-enable the PWA frontend.
2. **Preserve archive integrity**:
   - Keep `archive/pwa.tar.gz` and `archive/pwa/` intact for future unarchiving when Phase 4 of `ROADMAP.md` is resumed.
3. **Static fallback in `api_server.py`**:
   - `api_server.py` contains safe fallback routes that gracefully handle missing or archived PWA static assets.
