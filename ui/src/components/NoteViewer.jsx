import { useState } from 'react'
import { X, FileText, Folder, Calendar, Edit3, Save, Loader2, AlertCircle, Star, Share2, Check, Link } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { updateNote } from '../api/recall'
import { useFavorites } from '../hooks/useFavorites'

export default function NoteViewer({ note, onClose, onNoteUpdated }) {
  const [isEditing, setIsEditing] = useState(false)
  const [editContent, setEditContent] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [showCopied, setShowCopied] = useState(false)
  
  const { isFavorite, toggleFavorite } = useFavorites()

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

  const isPdf = file_path.toLowerCase().endsWith('.pdf')
  const isMarkdown = file_path.toLowerCase().endsWith('.md') || !file_path.includes('.')

  // Check if this note is favorited
  const favorited = isFavorite(file_path)

  const handleToggleFavorite = () => {
    toggleFavorite({
      file_path,
      title: displayTitle,
      vault
    })
  }

  const handleShare = async () => {
    // Build shareable URL
    const shareUrl = `${window.location.origin}/note?path=${encodeURIComponent(file_path)}`
    
    try {
      await navigator.clipboard.writeText(shareUrl)
      setShowCopied(true)
      setTimeout(() => setShowCopied(false), 2000)
    } catch (err) {
      // Fallback for older browsers
      const textArea = document.createElement('textarea')
      textArea.value = shareUrl
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)
      setShowCopied(true)
      setTimeout(() => setShowCopied(false), 2000)
    }
  }

  const handleStartEdit = () => {
    setEditContent(content)
    setIsEditing(true)
    setSaveError(null)
  }

  const handleCancelEdit = () => {
    setIsEditing(false)
    setEditContent('')
    setSaveError(null)
  }

  const handleSave = async () => {
    setIsSaving(true)
    setSaveError(null)
    
    try {
      await updateNote(file_path, editContent)
      setIsEditing(false)
      // Notify parent to refresh if needed
      if (onNoteUpdated) {
        onNoteUpdated(file_path, editContent)
      }
    } catch (err) {
      console.error('Failed to save note:', err)
      setSaveError(err.message || 'Failed to save')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div 
        className="bg-bg-secondary border border-border rounded-2xl w-full max-w-3xl max-h-[85vh] flex flex-col shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header - Stacked layout for better mobile UX */}
        <div className="p-4 border-b border-border space-y-2">
          {/* Row 1: Title + Close */}
          <div className="flex items-center gap-3">
            <FileText className="w-5 h-5 text-accent flex-shrink-0" />
            <h2 className="font-semibold truncate flex-1 min-w-0">{displayTitle}</h2>
            <button
              onClick={onClose}
              className="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-tertiary transition-colors flex-shrink-0"
              title="Close"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          
          {/* Row 2: Breadcrumb path + relevance */}
          <div className="flex items-center gap-2 text-sm text-text-secondary pl-8">
            <Folder className="w-3.5 h-3.5 flex-shrink-0" />
            <span className="truncate">{vault}{category && ` › ${category}`}</span>
            {relevance > 0 && (
              <>
                <span className="text-border flex-shrink-0">•</span>
                <span className={`flex-shrink-0 ${
                  relevance >= 80 ? 'text-green-400' : 
                  relevance >= 50 ? 'text-yellow-400' : 
                  'text-text-secondary'
                }`}>
                  {relevance}%
                </span>
              </>
            )}
          </div>
          
          {/* Row 3: Action buttons */}
          <div className="flex items-center gap-1 pl-8">
            {/* Favorite button */}
            <button
              onClick={handleToggleFavorite}
              className={`p-2 rounded-lg transition-colors ${
                favorited 
                  ? 'text-yellow-400 hover:bg-yellow-400/10' 
                  : 'text-text-secondary hover:text-yellow-400 hover:bg-bg-tertiary'
              }`}
              title={favorited ? 'Remove from favorites' : 'Add to favorites'}
            >
              <Star className={`w-4 h-4 ${favorited ? 'fill-yellow-400' : ''}`} />
            </button>

            {/* Share button */}
            <button
              onClick={handleShare}
              className={`p-2 rounded-lg transition-colors ${
                showCopied
                  ? 'text-green-400 bg-green-400/10'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-tertiary'
              }`}
              title={showCopied ? 'Link copied!' : 'Copy share link'}
            >
              {showCopied ? (
                <Check className="w-4 h-4" />
              ) : (
                <Link className="w-4 h-4" />
              )}
            </button>

            {/* Edit/Save buttons for markdown files */}
            {isMarkdown && !isPdf && (
              <>
                {isEditing ? (
                  <div className="flex items-center gap-1 ml-auto">
                    <button
                      onClick={handleCancelEdit}
                      disabled={isSaving}
                      className="px-3 py-1.5 rounded-lg text-sm text-text-secondary hover:text-text-primary hover:bg-bg-tertiary transition-colors disabled:opacity-50"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleSave}
                      disabled={isSaving}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm bg-accent hover:bg-accent-muted text-white transition-colors disabled:opacity-50"
                    >
                      {isSaving ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Save className="w-4 h-4" />
                      )}
                      Save
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={handleStartEdit}
                    className="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-tertiary transition-colors"
                    title="Edit note"
                  >
                    <Edit3 className="w-4 h-4" />
                  </button>
                )}
              </>
            )}
          </div>
        </div>

        {/* Save error */}
        {saveError && (
          <div className="mx-4 mt-4 flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{saveError}</span>
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {isEditing ? (
            <textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              className="w-full h-full min-h-[400px] bg-bg-primary border border-border rounded-lg p-4 font-mono text-sm resize-none focus:outline-none focus:border-accent/50"
              placeholder="Write your note in markdown..."
              autoFocus
            />
          ) : (
            <div className="prose-recall max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {content}
              </ReactMarkdown>
            </div>
          )}
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
            {isEditing && (
              <span className="text-xs text-accent">Editing mode</span>
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
