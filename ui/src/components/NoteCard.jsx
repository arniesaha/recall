import { FileText, Folder } from 'lucide-react'

export default function NoteCard({ result, onClick, isExpanded = false }) {
  const {
    file_path = '',
    title = '',
    excerpt = '',
    score = 0,
    vault = 'notes',
    category = '',
    date = ''
  } = result

  // Use title from API or extract from path
  const displayTitle = title || file_path.split('/').pop()?.replace(/\.[^.]+$/, '') || 'Untitled'
  
  // Format relevance score as percentage
  const relevance = Math.round((score || 0) * 100)
  
  // Clean up excerpt (remove HTML tags if any)
  const snippet = excerpt.replace(/<[^>]*>/g, '').substring(0, 250)

  return (
    <div
      onClick={onClick}
      className={`
        bg-bg-secondary border border-border rounded-xl p-4
        hover:border-accent/30 hover:bg-bg-secondary/80
        cursor-pointer transition-all duration-150
        animate-fade-in
        ${isExpanded ? 'ring-2 ring-accent' : ''}
      `}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <FileText className="w-4 h-4 text-accent flex-shrink-0" />
          <h3 className="font-medium truncate">{displayTitle}</h3>
        </div>
        <span className={`
          px-2 py-0.5 rounded text-xs font-medium flex-shrink-0
          ${relevance >= 80 ? 'bg-green-500/20 text-green-400' : 
            relevance >= 50 ? 'bg-yellow-500/20 text-yellow-400' : 
            'bg-bg-tertiary text-text-secondary'}
        `}>
          {relevance}%
        </span>
      </div>

      {/* Vault badge */}
      <div className="flex items-center gap-1.5 mb-3 text-sm text-text-secondary">
        <Folder className="w-3.5 h-3.5" />
        <span>{vault}</span>
        {category && (
          <>
            <span className="text-border">•</span>
            <span className="text-xs">{category}</span>
          </>
        )}
        {date && (
          <>
            <span className="text-border">•</span>
            <span className="text-xs">{date}</span>
          </>
        )}
      </div>

      {/* Snippet */}
      <p className="text-sm text-text-secondary line-clamp-3 leading-relaxed">
        {snippet}
      </p>
    </div>
  )
}
