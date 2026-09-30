# Frontend Design Document — Recall

## Aesthetic & Theme
- **Theme:** Dark observability tool aesthetic (inspired by Datadog, Grafana, Linear).
- **Primary Background:** Slate 900 (`#0f172a`) / Slate 950 (`#020617`).
- **Surface Elevation:** Slate 800 (`#1e293b`) with subtle borders (`#334155`).
- **Accent Color:** Cyan 500 (`#06b6d4`) / Cyan 400 (`#22d3ee`).
- **Success State:** Emerald 500 (`#10b981`).
- **Warning / Demotion State:** Amber 500 (`#f59e0b`).
- **Error State:** Rose 500 (`#f43f5e`).

## Typography
- **UI Sans:** `Inter`, system-ui, sans-serif for interface controls, headers, and body text.
- **Code / Monospace:** `JetBrains Mono`, `Fira Code`, `ui-monospace`, monospace for logs, alert queries, JSON payload previews, IDs, and code blocks.

## Spacing & Components
- **Borders & Shadows:** 1px subtle borders (`border-slate-800`), low-blur glow for accent highlights.
- **Icons:** `lucide-react` icons (16px / 20px) consistent across all status pills, action buttons, and navigation.
- **Interactive Elements:** Explicit `:hover`, `:focus`, `:active`, and `:disabled` states on all buttons, textareas, and interactive cards.
