# Recall Frontend Documentation

## Overview
The Recall frontend is built with React 19, Vite, TypeScript, and Tailwind CSS v4, providing an observability-tool style interface (dark theme, JetBrains Mono font for logs, Slate 950 surfaces, and Cyan accents) to interact with the Recall incident agent backend.

## Getting Started

### Prerequisites
- Node.js 18+ and npm
- Running Recall backend on `http://localhost:8000` (or configured URL)

### Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Default configuration:
```env
VITE_API_BASE_URL=http://localhost:8000
```

### Installation
```bash
cd frontend
npm install
```

### Development Server
```bash
npm run dev
```
The dev server runs at `http://localhost:5173`.

### Component Unit Tests
Runs Vitest + React Testing Library suite:
```bash
npm test
```

### Production Build
Type-checks and builds optimized static bundle in `dist/`:
```bash
npm run build
```

## Architecture & Components
1. **`AlertWorkbench`**: Main alert textarea with 5 sample log chips, Memory ON / Memory OFF / Compare Side-by-Side toggle, and submit controls.
2. **`SuggestionResult`**: Displays root cause with confidence bar, ranked fix steps with `prior_outcome` badges (`worked`, `failed`, `unknown`), source chips, `memory_status` distinct copy, and model status pill.
3. **`SourceDrawer`**: Slide-over panel displaying full details for recalled memories and per-arm scores (final, reranker, semantic, keyword).
4. **`MemoryPanel`**: Full list of recalled memories and an Observations tab fetching consolidated patterns from `/api/memory/observations`.
5. **`OutcomePanel`**: "Fixed" / "Didn't work" buttons + notes field, wired to `/api/outcome` and disabling buttons post-submit.
6. **`PostmortemDialog`**: Modal dialog to paste post-mortem markdown and view follow-up recall verification.
7. **`LearningCurvePage`**: Chart layout preview for Task 3 benchmark evaluation.
8. **`Header`**: Status bar polling `/api/health` every 30 seconds for Hindsight connection status and active LLM models.
