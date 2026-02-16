import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, FileText, Loader2, AlertCircle, Star, Share2, Check, Edit3, Save, Calendar, Folder } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getNote, updateNote } from '../api/recall'
import { useFavorites } from '../hooks/useFavorites'

export default function Note() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const path = searchParams.get('path')
  
  const [note, setNote] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [isEditing, setIsEditing] = useState(false)
  const [editContent, setEditContent] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [showCopied, setShowCopied] = useState(false)

  const { isFavorite, toggleFavorite } = useFavorites()

  useEffect(() => {
    async function fetchNote() {
      if (!path) {
        setError('No note path provided')
        setIsLoading(false)
        return
      }

      setIsLoading(true)
      setError(null)
      
      try {
        const data = await getNote(path)
        setNote({
          file_path: path,
          title: data.title || path.split('/').pop()?.replace(/\.[^.]+$/, '') || 'Untitled',
          content: data.content || '',
          vault: data.vault || 'work',
          modified: data.modified || '',
          source_type: data.source_type || 'markdown'
        })
      } catch (err) {
        console.error('Failed to fetch note:', err)
        setError(err.message || 'Failed to load note')
      } finally {
        setIsLoading(false)
      }
    }

    fetchNote()
  }, [path])

  const favorited = note ? isFavorite(note.file_path) : false

  const handleToggleFavorite = () => {
    if (!note) return
    toggleFavorite({
      file_path: note.file_path,
      title: note.title,
      vault: note.vault
    })
  }

  const handleShare = async () => {
    const shareUrl = window.location.href
    
    try {
      await navigator.clipboard.writeText(shareUrl)
      setShowCopied(true)
      setTimeout(() => setShowCopied(false), 2000)
    } catch (err) {
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
    setEditContent(note?.content || '')
    setIsEditing(true)
    setSaveError(null)
  }

  const handleCancelEdit = () => {
    setIsEditing(false)
    setEditContent('')
    setSaveError(null)
  }

  const handleSave = async () => {
    if (!note?.file_path) return
    
    setIsSaving(true)
    setSaveError(null)
    
    try {
      await updateNote(note.file_path, editContent)
      setNote(prev => ({ ...prev, content: editContent }))
      setIsEditing(false)
    } catch (err) {
      console.error('Failed to save note:', err)
      setSaveError(err.message || 'Failed to save')
    } finally {
      setIsSaving(false)
    }
  }

  const isMarkdown = note?.source_type === 'markdown'

  if (!path) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-6">
        <button
          onClick={() => navigate('/')}
          className="inline-flex items-center gap-1 text-text-secondary hover:text-text-primary mb-6 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span className="text-sm">Home</span>
        </button>

        <div className="bg-bg-secondary border border-border rounded-xl p-8 text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h2 className="text-xl font-semibold mb-2">No note specified</h2>
          <p className="text-text-secondary mb-4">
            Please provide a note path in the URL.
          </p>
          <button
            onClick={() => navigate('/')}
            className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent-muted transition-colors"
          >
            Search Notes
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <button
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-1 text-text-secondary hover:text-text-primary transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span className="text-sm">Back</span>
        </button>

        {note && (
          <div className="flex items-center gap-2">
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
              <Star className={`w-5 h-5 ${favorited ? 'fill-yellow-400' : ''}`} />
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
              {showCopied ? <Check className="w-5 h-5" /> : <Share2 className="w-5 h-5" />}
            </button>

            {/* Edit/Save buttons */}
            {isMarkdown && (
              <>
                {isEditing ? (
                  <>
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
                  </>
                ) : (
                  <button
                    onClick={handleStartEdit}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-text-secondary hover:text-text-primary hover:bg-bg-tertiary transition-colors"
                  >
                    <Edit3 className="w-4 h-4" />
                    Edit
                  </button>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-8 h-8 text-accent animate-spin" />
          <span className="ml-3 text-text-secondary">Loading note...</span>
        </div>
      )}

      {/* Error state */}
      {error && !isLoading && (
        <div className="bg-bg-secondary border border-border rounded-xl p-8 text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h2 className="text-xl font-semibold mb-2">Failed to load note</h2>
          <p className="text-text-secondary mb-4">{error}</p>
          <p className="text-sm text-text-secondary font-mono bg-bg-tertiary px-3 py-2 rounded mb-6">
            {path}
          </p>
          <button
            onClick={() => navigate('/')}
            className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent-muted transition-colors"
          >
            Search Notes
          </button>
        </div>
      )}

      {/* Note content */}
      {note && !isLoading && !error && (
        <div className="bg-bg-secondary border border-border rounded-xl overflow-hidden">
          {/* Note header */}
          <div className="p-6 border-b border-border">
            <div className="flex items-center gap-3 mb-2">
              <FileText className="w-6 h-6 text-accent" />
              <h1 className="text-2xl font-bold">{note.title}</h1>
            </div>
            <div className="flex items-center gap-4 text-sm text-text-secondary">
              <span className="flex items-center gap-1.5">
                <Folder className="w-4 h-4" />
                {note.vault}
              </span>
              {note.modified && (
                <span className="flex items-center gap-1.5">
                  <Calendar className="w-4 h-4" />
                  {new Date(note.modified).toLocaleDateString()}
                </span>
              )}
            </div>
          </div>

          {/* Save error */}
          {saveError && (
            <div className="mx-6 mt-4 flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{saveError}</span>
            </div>
          )}

          {/* Note body */}
          <div className="p-6">
            {isEditing ? (
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                className="w-full min-h-[400px] bg-bg-primary border border-border rounded-lg p-4 font-mono text-sm resize-none focus:outline-none focus:border-accent/50"
                placeholder="Write your note in markdown..."
                autoFocus
              />
            ) : (
              <div className="prose-recall max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {note.content}
                </ReactMarkdown>
              </div>
            )}
          </div>

          {/* Note footer */}
          <div className="px-6 py-4 border-t border-border bg-bg-tertiary/30">
            <p className="text-xs text-text-secondary font-mono truncate" title={note.file_path}>
              {note.file_path}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
