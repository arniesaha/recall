import { useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { AlertCircle, ArrowLeft } from 'lucide-react'
import SearchBar from '../components/SearchBar'
import SearchFilters from '../components/SearchFilters'
import AIAnswer from '../components/AIAnswer'
import SearchResults from '../components/SearchResults'
import NoteViewer from '../components/NoteViewer'
import { useSearch } from '../hooks/useSearch'
import { useRecentSearches } from '../hooks/useRecentSearches'

export default function Search() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const initialQuery = searchParams.get('q') || ''
  const initialVault = searchParams.get('vault') || 'work'
  
  const {
    query,
    vault,
    results,
    aiAnswer,
    isLoading,
    isAiLoading,
    error,
    detectedPerson,
    filters,
    performSearch,
    updateFilters,
    clearSearch
  } = useSearch()

  const { addSearch } = useRecentSearches()
  const [selectedNote, setSelectedNote] = useState(null)

  // Perform search on mount if query param exists
  useEffect(() => {
    if (initialQuery && initialQuery !== query) {
      addSearch(initialQuery)
      performSearch(initialQuery, initialVault, filters)
    }
  }, [initialQuery, initialVault])

  const handleSearch = (newQuery, newVault = 'work') => {
    addSearch(newQuery)
    navigate(`/search?q=${encodeURIComponent(newQuery)}&vault=${newVault}`, { replace: true })
    performSearch(newQuery, newVault, filters)
  }

  const handleFilterChange = (newFilters) => {
    updateFilters(newFilters)
    // Re-run search with new filters
    if (query) {
      const mergedFilters = { ...filters, ...newFilters }
      performSearch(query, vault, mergedFilters)
    }
  }

  const handleResultClick = (result, idx) => {
    setSelectedNote(result)
  }

  const handleCloseViewer = () => {
    setSelectedNote(null)
  }

  const handleNoteUpdated = (path, newContent) => {
    // Update the selected note content locally
    if (selectedNote && selectedNote.file_path === path) {
      setSelectedNote(prev => ({
        ...prev,
        content: newContent,
        excerpt: newContent
      }))
    }
    // Could also refresh results here if needed
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      {/* Back button */}
      <button
        onClick={() => navigate('/')}
        className="inline-flex items-center gap-1 text-text-secondary hover:text-text-primary mb-4 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span className="text-sm">Back</span>
      </button>

      {/* Search bar */}
      <div className="mb-4">
        <SearchBar
          onSearch={handleSearch}
          isLoading={isLoading}
          initialQuery={initialQuery}
          initialVault={initialVault}
          size="normal"
        />
      </div>

      {/* Filters */}
      <div className="mb-6">
        <SearchFilters
          onFilterChange={handleFilterChange}
          dateFilter={filters.dateFilter}
          dateFrom={filters.dateFrom}
          dateTo={filters.dateTo}
          personFilter={filters.personFilter}
        />
      </div>

      {/* Error state */}
      {error && (
        <div className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/30 rounded-xl mb-6 text-red-400">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <div>
            <p className="font-medium">Search failed</p>
            <p className="text-sm opacity-80">{error}</p>
          </div>
        </div>
      )}

      {/* AI Answer */}
      <AIAnswer
        answer={aiAnswer?.answer}
        sources={aiAnswer?.sources}
        isLoading={isAiLoading && !aiAnswer}
        detectedPerson={aiAnswer?.detectedPerson || detectedPerson}
        hasNoResults={aiAnswer?.hasNoResults || (results.length === 0 && !isLoading && query)}
      />

      {/* Search Results */}
      <SearchResults
        results={results}
        isLoading={isLoading && results.length === 0}
        onResultClick={handleResultClick}
        detectedPerson={detectedPerson}
      />

      {/* Empty state */}
      {!isLoading && !error && query && results.length === 0 && (
        <div className="text-center py-12 text-text-secondary">
          <p className="text-lg mb-2">No results found</p>
          <p className="text-sm">Try a different search query or adjust your filters</p>
        </div>
      )}

      {/* Note viewer modal */}
      {selectedNote && (
        <NoteViewer
          note={selectedNote}
          onClose={handleCloseViewer}
          onNoteUpdated={handleNoteUpdated}
        />
      )}
    </div>
  )
}
