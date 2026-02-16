import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Brain, Zap, Clock, Tag, X, History } from 'lucide-react'
import SearchBar from '../components/SearchBar'
import TagsList from '../components/TagsList'
import FavoritesList from '../components/FavoritesList'
import NoteViewer from '../components/NoteViewer'
import { useRecentSearches } from '../hooks/useRecentSearches'
import { getNote } from '../api/recall'

export default function Home() {
  const navigate = useNavigate()
  const { recentSearches, addSearch, removeSearch, clearSearches } = useRecentSearches()
  const [selectedNote, setSelectedNote] = useState(null)
  const [noteLoading, setNoteLoading] = useState(false)

  const handleSearch = (query, vault = 'work') => {
    addSearch(query)
    navigate(`/search?q=${encodeURIComponent(query)}&vault=${vault}`)
  }

  const handleTagClick = (tagName) => {
    // Search for notes with this tag
    handleSearch(`#${tagName}`)
  }

  const handleFavoriteClick = async (fav) => {
    setNoteLoading(true)
    try {
      const noteData = await getNote(fav.file_path)
      setSelectedNote({
        file_path: fav.file_path,
        title: noteData?.title || fav.title,
        content: noteData?.content || 'No content available',
        excerpt: noteData?.content || 'No content available',
        vault: fav.vault,
        modified: noteData?.modified || ''
      })
    } catch (err) {
      console.error('Failed to load favorite note:', err)
    } finally {
      setNoteLoading(false)
    }
  }

  const suggestedSearches = [
    'Action items from 1:1s',
    'Project timelines',
    'Meeting notes from last week'
  ]

  const quickFilters = [
    { label: 'Work', icon: Zap },
    { label: 'Personal', icon: Tag },
    { label: 'Recent', icon: Clock }
  ]

  return (
    <div className="max-w-2xl mx-auto px-4 py-12 md:py-24">
      {/* Hero */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-accent/10 mb-6">
          <Brain className="w-8 h-8 text-accent" />
        </div>
        <h1 className="text-3xl md:text-4xl font-bold mb-3">
          Search your knowledge
        </h1>
        <p className="text-text-secondary text-lg">
          Ask questions in natural language, get AI-powered answers from your notes.
        </p>
      </div>

      {/* Search bar */}
      <div className="mb-8">
        <SearchBar 
          onSearch={handleSearch} 
          autoFocus={true}
          size="large"
        />
      </div>

      {/* Recent searches from localStorage */}
      {recentSearches.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-text-secondary flex items-center gap-2">
              <History className="w-4 h-4" />
              Recent searches
            </h3>
            <button
              onClick={clearSearches}
              className="text-xs text-text-secondary hover:text-text-primary transition-colors"
            >
              Clear all
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {recentSearches.slice(0, 6).map((search, idx) => (
              <div
                key={idx}
                className="group flex items-center gap-1 px-3 py-1.5 bg-bg-secondary border border-border rounded-lg text-sm text-text-secondary hover:text-text-primary hover:border-accent/30 transition-colors"
              >
                <button
                  onClick={() => handleSearch(search)}
                  className="hover:text-accent"
                >
                  {search}
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    removeSearch(search)
                  }}
                  className="opacity-0 group-hover:opacity-100 p-0.5 hover:text-red-400 transition-all"
                  title="Remove"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Suggested searches */}
      <div className="mb-8">
        <h3 className="text-sm font-medium text-text-secondary mb-3">Try asking:</h3>
        <div className="flex flex-wrap gap-2">
          {suggestedSearches.map((search, idx) => (
            <button
              key={idx}
              onClick={() => handleSearch(search)}
              className="px-3 py-1.5 bg-bg-secondary border border-border rounded-lg text-sm text-text-secondary hover:text-text-primary hover:border-accent/30 transition-colors"
            >
              {search}
            </button>
          ))}
        </div>
      </div>

      {/* Quick filters */}
      <div>
        <h3 className="text-sm font-medium text-text-secondary mb-3">Quick filters:</h3>
        <div className="flex gap-2">
          {quickFilters.map((filter, idx) => (
            <button
              key={idx}
              onClick={() => handleSearch(`vault:${filter.label.toLowerCase()}`)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-bg-secondary border border-border rounded-lg text-sm hover:border-accent/30 transition-colors"
            >
              <filter.icon className="w-4 h-4 text-accent" />
              {filter.label}
            </button>
          ))}
        </div>
      </div>

      {/* Favorites section */}
      <div className="mt-8">
        <FavoritesList onNoteClick={handleFavoriteClick} maxVisible={4} />
      </div>

      {/* Tags section */}
      <div className="mt-8">
        <TagsList onTagClick={handleTagClick} maxVisible={10} />
      </div>

      {/* Features hint */}
      <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
        {[
          { title: 'Semantic Search', desc: 'Find by meaning, not just keywords' },
          { title: 'AI Answers', desc: 'Get synthesized answers from your notes' },
          { title: 'Fast Results', desc: 'Instant search across all your knowledge' }
        ].map((feature, idx) => (
          <div key={idx} className="p-4">
            <h4 className="font-medium mb-1">{feature.title}</h4>
            <p className="text-sm text-text-secondary">{feature.desc}</p>
          </div>
        ))}
      </div>

      {/* Note viewer modal for favorites */}
      {selectedNote && (
        <NoteViewer
          note={selectedNote}
          onClose={() => setSelectedNote(null)}
        />
      )}

      {/* Loading overlay */}
      {noteLoading && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-bg-secondary border border-border rounded-xl p-6 flex items-center gap-3">
            <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            <span>Loading note...</span>
          </div>
        </div>
      )}
    </div>
  )
}
