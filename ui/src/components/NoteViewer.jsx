import { X, FileText, Folder, Calendar, ExternalLink } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function NoteViewer({ note, onClose }) {
  if (!note) return null

  const {
    file_path = '',
    title = '',
    excerpt = '',
    content: noteContent = '',
    score = 0,
    vault = 'notes',
    category = '',
    date = '',
    modified = ''
  } = note

  // Use title from API or extract from path
  const displayTitle = title || file_path.split('/').pop()?.replace(/\.[^.]+$/, '') || 'Untitled'
  const relevance = Math.round((score || 0) * 100)
  // Use content or excerpt, clean HTML tags
  const rawContent = noteContent || excerpt || ''
  const content = rawContent.replace(/<[^>]*>/g, '')

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div 
        className="bg-bg-secondary border border-border rounded-2xl w-full max-w-3xl max-h-[85vh] flex flex-col shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-3 min-w-0">
            <FileText className="w-5 h-5 text-accent flex-shrink-0" />
            <div className="min-w-0">
              <h2 className="font-semibold truncate">{displayTitle}</h2>
              <div className="flex items-center gap-2 text-sm text-text-secondary">
                <Folder className="w-3.5 h-3.5" />
                <span>{vault}</span>
                {category && (
                  <>
                    <span className="text-border">•</span>
                    <span>{category}</span>
                  </>
                )}
                {relevance > 0 && (
                  <>
                    <span className="text-border">•</span>
                    <span className={`
                      ${relevance >= 80 ? 'text-green-400' : 
                        relevance >= 50 ? 'text-yellow-400' : 
                        'text-text-secondary'}
                    `}>
                      {relevance}% match
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-tertiary transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="prose-recall max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {content}
            </ReactMarkdown>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-border text-sm text-text-secondary">
          <div className="flex items-center gap-4">
            {(date || modified) && (
              <span className="flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5" />
                {date || (modified ? new Date(modified).toLocaleDateString() : '')}
              </span>
            )}
          </div>
          <span className="text-xs text-text-secondary/60 truncate max-w-[200px]" title={file_path}>
            {file_path}
          </span>
        </div>
      </div>

      {/* Click outside to close */}
      <div className="absolute inset-0 -z-10" onClick={onClose} />
    </div>
  )
}
