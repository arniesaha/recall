# Recall UI Design Plan

## Vision
A minimal, Obsidian-inspired knowledge search and viewing interface. Clean, fast, distraction-free.

---

## Design Principles

### 1. Obsidian-Inspired Minimalism
- **Monochrome + accent**: Dark background (#1e1e1e), light text, single accent color
- **Typography-first**: Content is king, UI fades into background
- **No chrome bloat**: Minimal buttons, no toolbars unless needed
- **Keyboard-first**: Power users can navigate entirely by keyboard

### 2. Reference Designs
| App | What to Borrow |
|-----|----------------|
| **Obsidian** | File tree, clean editor, subtle UI |
| **Raycast** | Command palette search UX |
| **Linear** | Minimal dark design, smooth animations |
| **Notion** | Clean reading view, mobile responsiveness |
| **Bear** | Tag-based organization, beautiful typography |

### 3. Core Interactions
- **Cmd+K / Ctrl+K**: Global search (always accessible)
- **Natural language**: "What did I discuss with Alex last week?"
- **Instant results**: Search-as-you-type with debouncing
- **Quick preview**: Hover/click to see full note without navigation

---

## Pages & Components

### 1. Search (Home)
```
┌─────────────────────────────────────────────────┐
│  🧠 Recall                          [⚙️]       │
├─────────────────────────────────────────────────┤
│                                                 │
│   ┌─────────────────────────────────────────┐   │
│   │ 🔍 Ask anything...                  ⌘K │   │
│   └─────────────────────────────────────────┘   │
│                                                 │
│   Recent searches:                              │
│   • 1:1 action items                            │
│   • Project Alpha timeline                      │
│   • Q4 planning notes                           │
│                                                 │
│   Quick filters: [Work] [Personal] [PDFs]       │
│                                                 │
└─────────────────────────────────────────────────┘
```

### 2. Search Results
```
┌─────────────────────────────────────────────────┐
│  🔍 "action items"                     [Clear] │
├─────────────────────────────────────────────────┤
│                                                 │
│  💬 AI Answer:                                  │
│  ┌─────────────────────────────────────────┐   │
│  │ Based on your notes, the main action    │   │
│  │ items are:                               │   │
│  │ 1. Finalize Q1 roadmap by Feb 15        │   │
│  │ 2. Review migration plan                 │   │
│  │ Sources: [2026-01-28], [2026-01-13]     │   │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  📄 Related Notes (5):                          │
│  ┌─────────────────────────────────────────┐   │
│  │ 📝 2026-01-28-weekly-sync              │   │
│  │ work/meetings • 85% match               │   │
│  │ "...discussed roadmap priorities..."    │   │
│  └─────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────┐   │
│  │ 📝 2026-01-13-team-standup             │   │
│  │ work/meetings • 78% match               │   │
│  └─────────────────────────────────────────┘   │
│                                                 │
└─────────────────────────────────────────────────┘
```

### 3. Note Viewer
```
┌─────────────────────────────────────────────────┐
│  ← Back    2026-01-28-weekly-sync      [Edit]  │
├─────────────────────────────────────────────────┤
│                                                 │
│  # Weekly Sync - Jan 28, 2026                  │
│                                                 │
│  ## Action Items                                │
│  - [ ] Finalize Q1 roadmap by Feb 15           │
│  - [x] Review migration plan                    │
│                                                 │
│  ## Discussion Notes                            │
│  Talked about the upcoming reorg and how       │
│  it affects the team...                         │
│                                                 │
│  ---                                            │
│  Tags: #meeting #planning                       │
│  Modified: Feb 1, 2026                          │
│                                                 │
└─────────────────────────────────────────────────┘
```

### 4. Note Editor (Simple)
```
┌─────────────────────────────────────────────────┐
│  ← Cancel   Editing: weekly-sync       [Save]  │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │ # Weekly Sync - Jan 28, 2026           │   │
│  │                                         │   │
│  │ ## Action Items                         │   │
│  │ - [ ] Finalize Q1 roadmap by Feb 15    │   │
│  │ - [x] Review migration plan            │   │
│  │ |                                       │   │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  Preview | Raw Markdown                         │
│                                                 │
└─────────────────────────────────────────────────┘
```

### 5. Browse (File Tree)
```
┌─────────────────────────────────────────────────┐
│  🧠 Recall    [Search] [Browse]                │
├─────────────────────────────────────────────────┤
│                                                 │
│  📁 work                                        │
│    📁 people                                    │
│      📁 alex (12 notes)                        │
│      📁 jordan (8 notes)                       │
│      📁 taylor (5 notes)                       │
│    📁 projects                                  │
│      📁 project-alpha                          │
│      📁 project-beta                           │
│    📁 meetings                                  │
│                                                 │
│  📁 personal                                    │
│    📁 journal                                   │
│    📁 ideas                                     │
│                                                 │
│  📄 PDFs (11 files)                            │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## Tech Stack

### Frontend
| Choice | Reasoning |
|--------|-----------|
| **React 18** | Mature ecosystem, good for SPAs |
| **Vite** | Fast builds, great DX |
| **TailwindCSS** | Utility-first, easy dark mode |
| **React Router** | Client-side routing |
| **React Query** | Data fetching + caching |
| **Zustand** | Lightweight state (if needed) |

### Markdown Rendering
| Option | Pros | Cons |
|--------|------|------|
| **react-markdown** | Simple, lightweight | Limited features |
| **@uiw/react-md-editor** | Editor + preview | Heavier |
| **Milkdown** | Beautiful, extensible | More complex |

**Recommendation**: Start with `react-markdown` + `remark-gfm` for viewing, add editor later.

### Build & Deploy
- **Docker**: Multi-stage build (node → nginx)
- **k8s**: Same pattern as other internal apps
- **Reverse proxy**: Via ingress or tunnel

---

## API Endpoints Needed

Current API supports search/query but needs:

### 1. GET /notes/{path}
Retrieve full note content by path.
```json
{
  "path": "work/meetings/2026-01-28.md",
  "title": "Weekly Sync",
  "content": "# Full markdown content...",
  "metadata": {
    "vault": "work",
    "modified": "2026-01-28T10:30:00Z",
    "tags": ["meeting", "planning"]
  }
}
```

### 2. PUT /notes/{path}
Update note content.
```json
{
  "content": "# Updated markdown..."
}
```

### 3. GET /notes/tree
Return file tree structure for browsing.
```json
{
  "work": {
    "people": {
      "alex": ["2026-01-28.md", "2026-01-13.md"],
      "jordan": ["2025-06-18.md"]
    }
  },
  "personal": { ... }
}
```

### 4. GET /notes/recent
Recent/frequently accessed notes.

---

## Color Palette

### Dark Mode (Primary)
```css
--bg-primary: #0d0d0d;      /* True black */
--bg-secondary: #1a1a1a;    /* Cards/panels */
--bg-tertiary: #262626;     /* Hover states */
--text-primary: #e5e5e5;    /* Main text */
--text-secondary: #a3a3a3;  /* Muted text */
--accent: #3b82f6;          /* Blue accent */
--accent-muted: #1d4ed8;    /* Accent hover */
--border: #333333;          /* Subtle borders */
--success: #22c55e;
--warning: #eab308;
--error: #ef4444;
```

### Light Mode (Optional)
```css
--bg-primary: #ffffff;
--bg-secondary: #f5f5f5;
--text-primary: #171717;
--text-secondary: #525252;
--accent: #2563eb;
```

---

## Typography

```css
/* Obsidian-inspired */
--font-ui: 'Inter', -apple-system, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', monospace;
--font-reading: 'Inter', sans-serif;

/* Scale */
--text-xs: 0.75rem;   /* 12px */
--text-sm: 0.875rem;  /* 14px */
--text-base: 1rem;    /* 16px */
--text-lg: 1.125rem;  /* 18px */
--text-xl: 1.25rem;   /* 20px */
--text-2xl: 1.5rem;   /* 24px */
```

---

## Responsive Breakpoints

```css
/* Mobile-first */
sm: 640px   /* Large phones */
md: 768px   /* Tablets */
lg: 1024px  /* Laptops */
xl: 1280px  /* Desktops */
```

### Mobile Adaptations
- Search bar fixed at top
- Results as full-width cards
- Bottom navigation (Search | Browse | Settings)
- Swipe gestures for back navigation

---

## MVP Scope (Phase 1)

### Must Have
- [x] Search page with natural language input
- [x] AI-generated answer display
- [x] Search results list with scores
- [x] Note viewer (markdown rendered)
- [x] Dark mode (default)
- [x] Mobile responsive
- [ ] Keyboard shortcuts (Cmd+K)

### Nice to Have (Phase 2)
- [ ] Note editing
- [ ] File tree browser
- [ ] Light mode toggle
- [ ] Recent searches history
- [ ] PDF viewer with page navigation
- [ ] Search filters (date, vault, person)

### Future (Phase 3)
- [ ] Create new notes
- [ ] Tags management
- [ ] Favorites/bookmarks
- [ ] Share note links
- [ ] Voice search

---

## Project Structure

```
recall-ui/
├── public/
│   └── favicon.svg
├── src/
│   ├── components/
│   │   ├── SearchBar.jsx
│   │   ├── SearchResults.jsx
│   │   ├── NoteCard.jsx
│   │   ├── NoteViewer.jsx
│   │   ├── AIAnswer.jsx
│   │   └── Layout.jsx
│   ├── pages/
│   │   ├── Home.jsx
│   │   ├── Search.jsx
│   │   └── Note.jsx
│   ├── hooks/
│   │   ├── useSearch.js
│   │   └── useNote.js
│   ├── api/
│   │   └── recall.js
│   ├── styles/
│   │   └── globals.css
│   ├── App.jsx
│   └── main.jsx
├── Dockerfile
├── package.json
├── tailwind.config.js
├── vite.config.js
└── README.md
```

---

## Estimated Timeline

| Phase | Scope | Time |
|-------|-------|------|
| **Phase 1** | Search + View (MVP) | 2-3 days |
| **Phase 2** | Edit + Browse | 2 days |
| **Phase 3** | Polish + Extras | 1-2 days |

---

## Recent Updates

### v1.1 - Temporal Search (2026-02-14)
Added date-aware filtering to search:
- "this week", "last month", "yesterday" auto-filter results
- Date range parameters in API (`date_from`, `date_to`)
- Cleaned query after temporal expression extraction

### v1.0 - MVP (2026-02-13)
- Search page with AI answers
- Note viewer with markdown rendering
- Browse page with folder navigation
- Dark mode, mobile responsive

---

*Last updated: 2026-02-14*
