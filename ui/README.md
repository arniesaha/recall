# Recall UI

A minimal, Obsidian-inspired knowledge search interface. Search your notes using natural language and get AI-powered answers.

## Features

- 🔍 **Semantic Search** - Find notes by meaning, not just keywords
- 🤖 **AI Answers** - Get synthesized answers from your knowledge base
- 📝 **Markdown Rendering** - Beautiful rendering of markdown content
- ⌨️ **Keyboard Shortcuts** - Press `⌘K` / `Ctrl+K` to focus search from anywhere
- 🌙 **Dark Mode** - Easy on the eyes, Obsidian-inspired design
- 📱 **Mobile Responsive** - Works great on all devices

## Quick Start

### Development

```bash
# Install dependencies
npm install

# Start dev server (proxies API to localhost:30889)
npm run dev

# Open http://localhost:3000
```

### Production Build

```bash
npm run build
npm run preview
```

### Docker

```bash
# Build image
docker build -t recall-ui .

# Run container
docker run -p 80:80 recall-ui
```

## Configuration

Environment variables (set in `.env` or at build time):

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `/api` | Backend API base URL |
| `VITE_API_TOKEN` | (built-in) | API authentication token |

## API Integration

The UI connects to the Recall API backend:

- `POST /search` - Semantic search across notes
- `POST /query` - RAG query with AI-generated answer

## Project Structure

```
src/
├── api/          # API client
├── components/   # Reusable UI components
│   ├── Layout.jsx
│   ├── SearchBar.jsx
│   ├── AIAnswer.jsx
│   ├── SearchResults.jsx
│   ├── NoteCard.jsx
│   └── NoteViewer.jsx
├── hooks/        # Custom React hooks
│   └── useSearch.js
├── pages/        # Route pages
│   ├── Home.jsx
│   ├── Search.jsx
│   └── Note.jsx
├── styles/       # Global styles
│   └── globals.css
├── App.jsx       # Main app component
└── main.jsx      # Entry point
```

## Tech Stack

- React 18 + Vite
- TailwindCSS (dark mode)
- React Router v6
- react-markdown + remark-gfm
- Lucide React (icons)

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `⌘K` / `Ctrl+K` | Focus search input |
| `Escape` | Close note viewer |
| `Enter` | Submit search |

## Color Palette

```css
--bg-primary: #0d0d0d;      /* Main background */
--bg-secondary: #1a1a1a;    /* Cards, panels */
--bg-tertiary: #262626;     /* Hover states */
--text-primary: #e5e5e5;    /* Main text */
--text-secondary: #a3a3a3;  /* Muted text */
--accent: #3b82f6;          /* Blue accent */
--border: #333333;          /* Borders */
```

## Future Roadmap

- [ ] Note editing
- [ ] File tree browser
- [ ] Light mode toggle
- [ ] Recent searches history
- [ ] PDF viewer
- [ ] Search filters (date, vault, tags)
- [ ] Voice search

---

Part of the [Recall](https://github.com/arnabsaha/recall) knowledge management system.
