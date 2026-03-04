import { Sparkles, ExternalLink, FolderOpen, User } from 'lucide-react'
import { Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/**
 * Post-process the AI answer to convert inline source citations like
 * "(Source: Reliability initiative planning with Vijay, 2026-03-02)"
 * into clickable markdown links pointing to /note?path=...
 */
function linkifySources(text, sources) {
  if (!text || !sources || sources.length === 0) return text

  // Build a lookup: normalize title → source object
  const sourceMap = new Map()
  for (const s of sources) {
    const title = (s.title || '').trim()
    if (title) {
      sourceMap.set(title.toLowerCase(), s)
      // Also index without date suffix for fuzzy match
      const noDate = title.replace(/\s*[-–]\s*\d{4}[-/]\d{2}[-/]\d{2}$/, '').trim()
      if (noDate) sourceMap.set(noDate.toLowerCase(), s)
    }
  }

  // Match patterns: (Source: <title>, <date>) or (Source: <title>)
  // Also handles **Source:** and variations
  return text.replace(
    /\((?:\*{0,2})Source:?\*{0,2}\s*([^,)]+?)(?:,\s*(\d{4}-\d{2}-\d{2}))?\)/gi,
    (match, rawTitle, date) => {
      const title = rawTitle.trim()
      const key = title.toLowerCase()
      
      // Try exact match, then fuzzy
      let source = sourceMap.get(key)
      if (!source) {
        // Try matching by checking if any source title contains this text or vice versa
        for (const [k, v] of sourceMap) {
          if (k.includes(key) || key.includes(k)) {
            source = v
            break
          }
        }
      }
      // Also try matching by date if title didn't match
      if (!source && date) {
        for (const s of sources) {
          if (s.date === date) {
            const sTitle = (s.title || '').toLowerCase()
            // Check partial overlap
            const words = key.split(/\s+/)
            const matchCount = words.filter(w => sTitle.includes(w)).length
            if (matchCount >= words.length * 0.5) {
              source = s
              break
            }
          }
        }
      }

      if (source) {
        const filePath = (source.file || '').replace(/^\/data\/obsidian\//, '')
        const noteUrl = `/note?path=${encodeURIComponent(filePath)}`
        const displayDate = date || source.date || ''
        const label = displayDate ? `${title}, ${displayDate}` : title
        return `([${label}](${noteUrl}))`
      }
      
      return match // No match found, leave as-is
    }
  )
}

export default function AIAnswer({ 
  answer, 
  sources = [], 
  isLoading = false,
  detectedPerson = null,
  hasNoResults = false
}) {
  if (isLoading) {
    return (
      <div className="bg-bg-secondary border border-border rounded-xl p-5 mb-6 animate-pulse-subtle">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles className="w-5 h-5 text-accent" />
          <span className="font-medium">AI Answer</span>
        </div>
        <div className="space-y-2">
          <div className="h-4 bg-bg-tertiary rounded w-full"></div>
          <div className="h-4 bg-bg-tertiary rounded w-5/6"></div>
          <div className="h-4 bg-bg-tertiary rounded w-4/6"></div>
        </div>
      </div>
    )
  }

  if (!answer) return null

  return (
    <div className="bg-bg-secondary border border-accent/30 rounded-xl p-5 mb-6 animate-fade-in">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles className="w-5 h-5 text-accent" />
        <span className="font-medium">AI Answer</span>
        {detectedPerson && (
          <span className="ml-auto flex items-center gap-1 text-xs text-text-secondary bg-bg-tertiary px-2 py-1 rounded-full">
            <User className="w-3 h-3" />
            {detectedPerson}
          </span>
        )}
      </div>

      <div className="prose-recall">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            // Render links with React Router navigation + accent styling
            a: ({ href, children, ...props }) => {
              if (href?.startsWith('/note')) {
                return (
                  <Link to={href} className="text-accent hover:text-accent-muted underline decoration-accent/40 hover:decoration-accent transition-colors" {...props}>
                    {children}
                  </Link>
                )
              }
              return <a href={href} className="text-accent hover:text-accent-muted underline" target="_blank" rel="noopener noreferrer" {...props}>{children}</a>
            }
          }}
        >
          {linkifySources(answer, sources)}
        </ReactMarkdown>
      </div>

      {/* Person-specific browse suggestion when no results */}
      {hasNoResults && detectedPerson && (
        <div className="mt-4 pt-4 border-t border-border">
          <div className="flex items-center gap-2 p-3 bg-accent/10 border border-accent/20 rounded-lg">
            <FolderOpen className="w-5 h-5 text-accent flex-shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium">Try browsing directly</p>
              <p className="text-xs text-text-secondary mt-0.5">
                Notes for {detectedPerson} might be in a folder not yet indexed
              </p>
            </div>
            <Link
              to={`/browse?expand=people/${detectedPerson.toLowerCase()}`}
              className="px-3 py-1.5 bg-accent hover:bg-accent-muted text-white text-sm rounded-lg transition-colors flex items-center gap-1"
            >
              <FolderOpen className="w-4 h-4" />
              Browse
            </Link>
          </div>
        </div>
      )}

      {sources && sources.length > 0 && (
        <div className="mt-4 pt-4 border-t border-border">
          <div className="text-sm font-medium text-accent mb-2">📎 Sources ({Math.min(sources.length, 5)} of {sources.length})</div>
          <div className="flex flex-col gap-2">
            {sources.slice(0, 5).map((source, idx) => {
              // Convert absolute path to API-compatible path
              const filePath = (source.file || '')
                .replace(/^\/data\/obsidian\//, '')
              const noteUrl = filePath ? `/note?path=${encodeURIComponent(filePath)}` : '#'
              const displayTitle = source.title || source.file?.split('/').pop()?.replace('.md', '') || `Source ${idx + 1}`
              const displayDate = source.date || null
              
              return (
                <Link
                  key={idx}
                  to={noteUrl}
                  className="flex items-center gap-3 px-3 py-2 bg-bg-tertiary rounded-lg hover:bg-bg-tertiary/80 hover:border-accent/40 border border-transparent transition-all group"
                >
                  <ExternalLink className="w-4 h-4 text-text-secondary group-hover:text-accent flex-shrink-0 transition-colors" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-text-primary group-hover:text-accent transition-colors truncate">
                      {displayTitle}
                    </div>
                    {displayDate && (
                      <div className="text-xs text-text-secondary mt-0.5">{displayDate}</div>
                    )}
                  </div>
                  {source.vault && (
                    <span className="text-xs text-text-secondary bg-bg-secondary px-2 py-0.5 rounded flex-shrink-0">
                      {source.vault}
                    </span>
                  )}
                </Link>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
