import { FileSearch, User, FolderOpen } from 'lucide-react'
import { Link } from 'react-router-dom'
import NoteCard from './NoteCard'
import { extractPersonFromPath } from '../utils/personDetection'

export default function SearchResults({ 
  results = [], 
  isLoading = false,
  onResultClick,
  selectedIndex = -1,
  detectedPerson = null
}) {
  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-text-secondary mb-4">
          <FileSearch className="w-5 h-5" />
          <span>Searching...</span>
        </div>
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-bg-secondary border border-border rounded-xl p-4 animate-pulse">
            <div className="h-5 bg-bg-tertiary rounded w-1/3 mb-3"></div>
            <div className="h-4 bg-bg-tertiary rounded w-1/4 mb-3"></div>
            <div className="space-y-2">
              <div className="h-3 bg-bg-tertiary rounded w-full"></div>
              <div className="h-3 bg-bg-tertiary rounded w-5/6"></div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (results.length === 0) {
    return null
  }

  // Find unique people mentioned in results
  const peopleInResults = [...new Set(
    results
      .map(r => extractPersonFromPath(r.file_path || r.path || ''))
      .filter(Boolean)
  )]

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-text-secondary">
          <FileSearch className="w-5 h-5" />
          <span>{results.length} related note{results.length !== 1 ? 's' : ''}</span>
        </div>
        
        {/* Quick links to browse by person */}
        {peopleInResults.length > 0 && (
          <div className="flex items-center gap-2">
            {peopleInResults.slice(0, 3).map(person => (
              <Link
                key={person}
                to={`/browse?expand=people/${person.toLowerCase()}`}
                className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-bg-tertiary hover:bg-accent/20 border border-border hover:border-accent/30 rounded-full text-text-secondary hover:text-accent transition-colors"
                title={`See all notes with ${person}`}
              >
                <User className="w-3 h-3" />
                All {person} notes
              </Link>
            ))}
          </div>
        )}
      </div>

      <div className="grid gap-3">
        {results.map((result, idx) => {
          const personFromPath = extractPersonFromPath(result.file_path || result.path || '')
          return (
            <div key={result.id || result.path || idx} className="relative">
              <NoteCard
                result={result}
                onClick={() => onResultClick?.(result, idx)}
                isExpanded={selectedIndex === idx}
              />
              {/* Show person badge on card if from a person folder */}
              {personFromPath && (
                <Link
                  to={`/browse?expand=people/${personFromPath.toLowerCase()}`}
                  className="absolute top-3 right-3 inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-accent/10 border border-accent/20 rounded-full text-accent hover:bg-accent/20 transition-colors"
                  onClick={(e) => e.stopPropagation()}
                  title={`Browse all ${personFromPath} notes`}
                >
                  <User className="w-3 h-3" />
                  {personFromPath}
                </Link>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
