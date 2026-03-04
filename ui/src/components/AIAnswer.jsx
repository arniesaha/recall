import { Sparkles, ExternalLink, FolderOpen, User } from 'lucide-react'
import { Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/**
 * Post-process the AI answer to convert inline source citations into
 * clickable markdown links pointing to /note?path=...
 *
 * Gemini produces several citation formats:
 *   1. (Source 1, 3: "Reliability initiative planning with Vijay")
 *   2. (Source: Reliability initiative planning with Vijay, 2026-03-02)
 *   3. **Title (2026-03-02, Source 3, 17):**
 */
function linkifySources(text, sources) {
  if (!text || !sources || sources.length === 0) return text

  // Build lookups
  const sourceMap = new Map()        // title → source
  const sourceByIndex = new Map()    // 1-based index → source
  for (let i = 0; i < sources.length; i++) {
    const s = sources[i]
    sourceByIndex.set(i + 1, s)
    const title = (s.title || '').trim()
    if (title) {
      sourceMap.set(title.toLowerCase(), s)
      // Also without trailing date
      const noDate = title.replace(/\s*[-–]\s*\d{4}[-/]\d{2}[-/]\d{2}$/, '').trim()
      if (noDate) sourceMap.set(noDate.toLowerCase(), s)
    }
  }

  function findSourceByTitle(rawTitle) {
    const key = rawTitle.toLowerCase().trim()
    let source = sourceMap.get(key)
    if (source) return source
    // Fuzzy: check containment
    for (const [k, v] of sourceMap) {
      if (k.includes(key) || key.includes(k)) return v
    }
    // Word overlap
    const words = key.split(/\s+/).filter(w => w.length > 2)
    let bestMatch = null, bestScore = 0
    for (const [k, v] of sourceMap) {
      const matchCount = words.filter(w => k.includes(w)).length
      const score = matchCount / words.length
      if (score > bestScore && score >= 0.5) {
        bestScore = score
        bestMatch = v
      }
    }
    return bestMatch
  }

  function sourceToLink(source, label) {
    const filePath = (source.file || '').replace(/^\/data\/obsidian\//, '')
    const noteUrl = `/note?path=${encodeURIComponent(filePath)}`
    return `[${label}](${noteUrl})`
  }

  let result = text

  // Pattern 1: (Source 1, 3: "Title here") or (Source 1: "Title here")
  result = result.replace(
    /\(Source\s+([\d,\s]+):\s*"([^"]+)"\)/gi,
    (match, nums, title) => {
      const source = findSourceByTitle(title)
      if (source) return `(${sourceToLink(source, title)})`
      return match
    }
  )

  // Pattern 2: (Source: Title, 2026-03-02) or (Source: Title)
  result = result.replace(
    /\(Source:\s*([^,)]+?)(?:,\s*(\d{4}-\d{2}-\d{2}))?\)/gi,
    (match, rawTitle, date) => {
      const title = rawTitle.trim()
      const source = findSourceByTitle(title)
      if (source) {
        const d = date || source.date || ''
        const label = d ? `${title}, ${d}` : title
        return `(${sourceToLink(source, label)})`
      }
      return match
    }
  )

  // Pattern 3: **Bold Title (2026-03-02, Source 3, 17):**
  // or: **Bold Title** (2026-03-02, Source 3, 17):
  // Convert the whole header into a link
  result = result.replace(
    /\*\*([^*]+?)\*\*\s*\((\d{4}-\d{2}-\d{2}),\s*Source\s+[\d,\s]+\):?/gi,
    (match, title, date) => {
      const source = findSourceByTitle(title.trim())
      if (source) return `**${sourceToLink(source, `${title.trim()}, ${date}`)}:**`
      return match
    }
  )

  // Pattern 3b: **Bold Title (2026-03-02, Source 3, 17):**  (title includes the parens inside bold)
  result = result.replace(
    /\*\*([^*(]+?)\s*\((\d{4}-\d{2}-\d{2}),\s*Source\s+[\d,\s]+\):?\*\*/gi,
    (match, title, date) => {
      const source = findSourceByTitle(title.trim())
      if (source) return `**${sourceToLink(source, `${title.trim()}, ${date}`)}:**`
      return match
    }
  )

  // Pattern 4: standalone (Source N) or (Source N, M) without title — link by index
  result = result.replace(
    /\(Source\s+(\d+)(?:,\s*\d+)*\)/gi,
    (match, firstNum) => {
      const idx = parseInt(firstNum, 10)
      const source = sourceByIndex.get(idx)
      if (source) {
        const label = source.title || `Source ${idx}`
        return `(${sourceToLink(source, label)})`
      }
      return match
    }
  )

  return result
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
