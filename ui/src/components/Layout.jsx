import { Link, useLocation } from 'react-router-dom'
import { Brain, Search, FolderTree, Settings } from 'lucide-react'

export default function Layout({ children }) {
  const location = useLocation()
  const isHome = location.pathname === '/'
  const isBrowse = location.pathname === '/browse'

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-border bg-bg-secondary/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
            <Brain className="w-6 h-6 text-accent" />
            <span className="font-semibold text-lg">Recall</span>
          </Link>

          <nav className="flex items-center gap-2">
            <Link
              to="/"
              className={`p-2 rounded-lg transition-colors ${
                isHome ? 'bg-bg-tertiary text-text-primary' : 'text-text-secondary hover:text-text-primary hover:bg-bg-tertiary'
              }`}
              title="Search"
            >
              <Search className="w-5 h-5" />
            </Link>
            <Link
              to="/browse"
              className={`p-2 rounded-lg transition-colors ${
                isBrowse ? 'bg-bg-tertiary text-text-primary' : 'text-text-secondary hover:text-text-primary hover:bg-bg-tertiary'
              }`}
              title="Browse"
            >
              <FolderTree className="w-5 h-5" />
            </Link>
            <button
              className="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-tertiary transition-colors"
              title="Settings"
            >
              <Settings className="w-5 h-5" />
            </button>
          </nav>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1">
        {children}
      </main>

      {/* Footer */}
      <footer className="border-t border-border py-4 px-4 text-center text-text-secondary text-sm">
        <span className="opacity-60">
          Press <kbd className="px-1.5 py-0.5 bg-bg-tertiary rounded text-xs font-mono mx-1">⌘K</kbd> to search
        </span>
      </footer>
    </div>
  )
}
