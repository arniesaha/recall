import { useState, useEffect } from 'react'
import { X, Save, Loader2, AlertCircle, FileText, FolderOpen, Eye, Code } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { createNote, getFolders } from '../api/recall'

export default function CreateNoteModal({ isOpen, onClose, onNoteCreated }) {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [vault, setVault] = useState('work')
  const [folder, setFolder] = useState('')
  const [folders, setFolders] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [isFoldersLoading, setIsFoldersLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showPreview, setShowPreview] = useState(false)

  // Fetch folders when vault changes
  useEffect(() => {
    async function fetchFolders() {
      if (!isOpen) return
      setIsFoldersLoading(true)
      try {
        const data = await getFolders(vault)
        setFolders(data.folders || [])
      } catch (err) {
        console.error('Failed to fetch folders:', err)
        setFolders([])
      } finally {
        setIsFoldersLoading(false)
      }
    }
    fetchFolders()
  }, [vault, isOpen])

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setTitle('')
      setContent('')
      setFolder('')
      setError(null)
      setShowPreview(false)
    }
  }, [isOpen])

  const handleSubmit = async (e) => {
    e.preventDefault()
    
    if (!title.trim()) {
      setError('Title is required')
      return
    }
    
    setIsLoading(true)
    setError(null)
    
    try {
      // Add title as H1 header if content doesn't already start with it
      let finalContent = content
      if (!content.trim().startsWith('# ')) {
        finalContent = `# ${title.trim()}\n\n${content}`
      }
      
      const result = await createNote(title.trim(), finalContent, vault, folder || null)
      
      if (onNoteCreated) {
        onNoteCreated(result)
      }
      
      onClose()
    } catch (err) {
      console.error('Failed to create note:', err)
      setError(err.message || 'Failed to create note')
    } finally {
      setIsLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div 
        className="bg-bg-secondary border border-border rounded-2xl w-full max-w-2xl max-h-[85vh] flex flex-col shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-3">
            <FileText className="w-5 h-5 text-accent" />
            <h2 className="font-semibold text-lg">Create New Note</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-tertiary transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Title */}
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1.5">
                Title <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Meeting notes, Ideas, Journal entry..."
                className="w-full px-4 py-2.5 bg-bg-primary border border-border rounded-lg focus:outline-none focus:border-accent/50 transition-colors"
                autoFocus
              />
            </div>

            {/* Vault and Folder row */}
            <div className="grid grid-cols-2 gap-4">
              {/* Vault selector */}
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1.5">
                  Vault
                </label>
                <select
                  value={vault}
                  onChange={(e) => {
                    setVault(e.target.value)
                    setFolder('')
                  }}
                  className="w-full px-4 py-2.5 bg-bg-primary border border-border rounded-lg focus:outline-none focus:border-accent/50 transition-colors appearance-none cursor-pointer"
                >
                  <option value="work">Work</option>
                  <option value="personal">Personal</option>
                </select>
              </div>

              {/* Folder selector */}
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1.5">
                  <span className="flex items-center gap-1.5">
                    <FolderOpen className="w-4 h-4" />
                    Folder
                  </span>
                </label>
                <select
                  value={folder}
                  onChange={(e) => setFolder(e.target.value)}
                  disabled={isFoldersLoading}
                  className="w-full px-4 py-2.5 bg-bg-primary border border-border rounded-lg focus:outline-none focus:border-accent/50 transition-colors appearance-none cursor-pointer disabled:opacity-50"
                >
                  <option value="">Root folder</option>
                  {folders.map((f) => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Content with preview toggle */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-sm font-medium text-text-secondary">
                  Content
                </label>
                <div className="flex items-center gap-1 bg-bg-tertiary rounded-lg p-0.5">
                  <button
                    type="button"
                    onClick={() => setShowPreview(false)}
                    className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
                      !showPreview ? 'bg-bg-primary text-text-primary' : 'text-text-secondary hover:text-text-primary'
                    }`}
                  >
                    <Code className="w-3 h-3" />
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowPreview(true)}
                    className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
                      showPreview ? 'bg-bg-primary text-text-primary' : 'text-text-secondary hover:text-text-primary'
                    }`}
                  >
                    <Eye className="w-3 h-3" />
                    Preview
                  </button>
                </div>
              </div>
              
              {showPreview ? (
                <div className="w-full min-h-[250px] bg-bg-primary border border-border rounded-lg p-4 prose-recall overflow-y-auto">
                  {content ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {`# ${title || 'Untitled'}\n\n${content}`}
                    </ReactMarkdown>
                  ) : (
                    <p className="text-text-secondary italic">Preview will appear here...</p>
                  )}
                </div>
              ) : (
                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="Write your note in markdown...

## Use headings for sections
- Bullet points work great
- Add #tags for organization

**Bold** and *italic* for emphasis"
                  className="w-full min-h-[250px] bg-bg-primary border border-border rounded-lg p-4 font-mono text-sm resize-none focus:outline-none focus:border-accent/50 transition-colors"
                />
              )}
            </div>

            {/* Error */}
            {error && (
              <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between p-4 border-t border-border">
            <p className="text-xs text-text-secondary">
              Supports Markdown formatting
            </p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onClose}
                disabled={isLoading}
                className="px-4 py-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-tertiary transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isLoading || !title.trim()}
                className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-muted text-white rounded-lg transition-colors disabled:opacity-50"
              >
                {isLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                Create Note
              </button>
            </div>
          </div>
        </form>
      </div>

      {/* Click outside to close */}
      <div className="absolute inset-0 -z-10" onClick={onClose} />
    </div>
  )
}
