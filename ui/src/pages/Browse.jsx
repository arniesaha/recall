import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { FolderTree, Loader2, AlertCircle, ChevronRight, Home, User } from 'lucide-react'
import FileTree from '../components/FileTree'
import NoteViewer from '../components/NoteViewer'
import { getNotesTree, getNote } from '../api/recall'

export default function Browse() {
  const [searchParams] = useSearchParams()
  const [tree, setTree] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedFile, setSelectedFile] = useState(null)
  const [noteContent, setNoteContent] = useState(null)
  const [noteLoading, setNoteLoading] = useState(false)
  const [expandPath, setExpandPath] = useState(null)
  
  // Get expand path from URL params
  const expandParam = searchParams.get('expand')

  // Fetch tree on mount
  useEffect(() => {
    async function fetchTree() {
      try {
        setLoading(true)
        setError(null)
        const data = await getNotesTree()
        setTree(data)
        
        // Set expand path from URL param
        if (expandParam) {
          setExpandPath(expandParam)
        }
      } catch (err) {
        console.error('Failed to fetch tree:', err)
        setError(err.message || 'Failed to load file tree')
      } finally {
        setLoading(false)
      }
    }
    fetchTree()
  }, [expandParam])

  // Handle file selection
  const handleFileClick = async (filePath) => {
    setSelectedFile(filePath)
    setNoteLoading(true)
    
    try {
      const note = await getNote(filePath)
      // Pass API response with content mapped to excerpt for NoteViewer
      setNoteContent({
        file_path: filePath,
        title: note?.title || filePath.split('/').pop()?.replace(/\.[^.]+$/, '') || 'Untitled',
        excerpt: note?.content || 'No content available',
        content: note?.content || 'No content available',
        vault: filePath.split('/')[0] || 'notes',
        category: filePath.split('/').slice(1, -1).join('/') || '',
        modified: note?.modified || ''
      })
    } catch (err) {
      console.error('Failed to fetch note:', err)
      setNoteContent({
        file_path: filePath,
        title: filePath.split('/').pop()?.replace(/\.[^.]+$/, '') || 'Untitled',
        excerpt: `Failed to load note: ${err.message}`,
        content: `Failed to load note: ${err.message}`,
        vault: filePath.split('/')[0] || 'notes'
      })
    } finally {
      setNoteLoading(false)
    }
  }

  const handleCloseViewer = () => {
    setNoteContent(null)
    setSelectedFile(null)
  }

  // Parse breadcrumb from selected file path
  const breadcrumbs = selectedFile ? selectedFile.split('/') : []

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <FolderTree className="w-6 h-6 text-accent" />
          <h1 className="text-2xl font-bold">Browse Notes</h1>
        </div>
        <p className="text-text-secondary">
          Navigate your knowledge base by folder structure
        </p>
      </div>

      {/* Breadcrumb (shown when a file is selected) */}
      {selectedFile && (
        <div className="flex items-center gap-1 mb-4 text-sm overflow-x-auto pb-2">
          <button 
            onClick={handleCloseViewer}
            className="flex items-center gap-1 text-text-secondary hover:text-text-primary transition-colors"
          >
            <Home className="w-4 h-4" />
          </button>
          {breadcrumbs.map((crumb, idx) => (
            <span key={idx} className="flex items-center gap-1">
              <ChevronRight className="w-4 h-4 text-text-secondary/50" />
              <span className={idx === breadcrumbs.length - 1 ? 'text-accent font-medium' : 'text-text-secondary'}>
                {crumb.replace(/\.[^.]+$/, '')}
              </span>
            </span>
          ))}
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-8 h-8 text-accent animate-spin" />
          <span className="ml-3 text-text-secondary">Loading file tree...</span>
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="flex items-center justify-center py-16">
          <div className="text-center">
            <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium mb-2">Failed to load files</h3>
            <p className="text-text-secondary mb-4">{error}</p>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-accent hover:bg-accent-muted text-white rounded-lg transition-colors"
            >
              Try Again
            </button>
          </div>
        </div>
      )}

      {/* Person filter indicator */}
      {expandParam && (
        <div className="mb-4 flex items-center gap-2 p-3 bg-accent/10 border border-accent/20 rounded-lg">
          <User className="w-5 h-5 text-accent" />
          <span className="text-sm">
            Showing folder: <span className="font-medium text-accent">{expandParam}</span>
          </span>
        </div>
      )}

      {/* File tree */}
      {!loading && !error && (
        <div className="bg-bg-secondary border border-border rounded-xl p-4">
          <FileTree 
            tree={tree} 
            onFileClick={handleFileClick}
            selectedFile={selectedFile}
            expandPath={expandPath}
          />
        </div>
      )}

      {/* Note viewer modal */}
      {noteContent && (
        <NoteViewer 
          note={noteContent} 
          onClose={handleCloseViewer} 
        />
      )}

      {/* Loading overlay for note content */}
      {noteLoading && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-bg-secondary border border-border rounded-xl p-6 flex items-center gap-3">
            <Loader2 className="w-5 h-5 text-accent animate-spin" />
            <span>Loading note...</span>
          </div>
        </div>
      )}
    </div>
  )
}
