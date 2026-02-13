import { useSearchParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, FileText } from 'lucide-react'

export default function Note() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const path = searchParams.get('path')

  // For now, redirect to search since we don't have a GET /notes/{path} endpoint
  // This page will be expanded when that API is available

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      <button
        onClick={() => navigate(-1)}
        className="inline-flex items-center gap-1 text-text-secondary hover:text-text-primary mb-6 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span className="text-sm">Back</span>
      </button>

      <div className="bg-bg-secondary border border-border rounded-xl p-8 text-center">
        <FileText className="w-12 h-12 text-text-secondary mx-auto mb-4" />
        <h2 className="text-xl font-semibold mb-2">Note Viewer</h2>
        <p className="text-text-secondary mb-4">
          Direct note viewing will be available once the API supports fetching notes by path.
        </p>
        {path && (
          <p className="text-sm text-text-secondary font-mono bg-bg-tertiary px-3 py-2 rounded">
            {path}
          </p>
        )}
        <button
          onClick={() => navigate('/')}
          className="mt-6 px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent-muted transition-colors"
        >
          Search Notes
        </button>
      </div>
    </div>
  )
}
