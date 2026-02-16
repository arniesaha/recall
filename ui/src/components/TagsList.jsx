import { useState, useEffect } from 'react'
import { Tag, Loader2, ChevronDown, ChevronUp } from 'lucide-react'
import { getTags } from '../api/recall'

export default function TagsList({ onTagClick, maxVisible = 12, vault = 'all' }) {
  const [tags, setTags] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [showAll, setShowAll] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    async function fetchTags() {
      setIsLoading(true)
      setError(null)
      try {
        const data = await getTags(vault, 50)
        setTags(data.tags || [])
      } catch (err) {
        console.error('Failed to fetch tags:', err)
        setError('Failed to load tags')
      } finally {
        setIsLoading(false)
      }
    }
    fetchTags()
  }, [vault])

  const handleTagClick = (tagName) => {
    if (onTagClick) {
      onTagClick(tagName)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-text-secondary text-sm">
        <Loader2 className="w-4 h-4 animate-spin" />
        <span>Loading tags...</span>
      </div>
    )
  }

  if (error || tags.length === 0) {
    return null // Don't show anything if no tags
  }

  const visibleTags = showAll ? tags : tags.slice(0, maxVisible)
  const hasMore = tags.length > maxVisible

  // Color coding based on count (most used = brighter)
  const getTagColor = (count) => {
    const maxCount = tags[0]?.count || 1
    const ratio = count / maxCount
    
    if (ratio > 0.7) return 'bg-accent/20 text-accent border-accent/30'
    if (ratio > 0.4) return 'bg-accent/10 text-accent/80 border-accent/20'
    return 'bg-bg-tertiary text-text-secondary border-border'
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <Tag className="w-4 h-4 text-accent" />
        <h3 className="text-sm font-medium text-text-secondary">Tags</h3>
        {tags.length > 0 && (
          <span className="text-xs text-text-secondary/60">({tags.length})</span>
        )}
      </div>
      
      <div className="flex flex-wrap gap-2">
        {visibleTags.map((tag) => (
          <button
            key={tag.name}
            onClick={() => handleTagClick(tag.name)}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-sm border transition-all hover:scale-105 ${getTagColor(tag.count)}`}
            title={`${tag.count} note${tag.count > 1 ? 's' : ''}`}
          >
            <span className="text-xs opacity-60">#</span>
            {tag.name}
            <span className="text-xs opacity-50">({tag.count})</span>
          </button>
        ))}
        
        {hasMore && (
          <button
            onClick={() => setShowAll(!showAll)}
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-sm text-text-secondary hover:text-text-primary hover:bg-bg-tertiary border border-border transition-colors"
          >
            {showAll ? (
              <>
                <ChevronUp className="w-3 h-3" />
                Show less
              </>
            ) : (
              <>
                <ChevronDown className="w-3 h-3" />
                +{tags.length - maxVisible} more
              </>
            )}
          </button>
        )}
      </div>
    </div>
  )
}
