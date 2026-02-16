import { Star, FileText, X, Trash2 } from 'lucide-react'
import { useFavorites } from '../hooks/useFavorites'

export default function FavoritesList({ onNoteClick, maxVisible = 6 }) {
  const { favorites, removeFavorite, clearFavorites } = useFavorites()

  if (favorites.length === 0) {
    return null
  }

  const visibleFavorites = favorites.slice(0, maxVisible)

  const handleNoteClick = (fav) => {
    if (onNoteClick) {
      onNoteClick({
        file_path: fav.file_path,
        title: fav.title,
        vault: fav.vault
      })
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Star className="w-4 h-4 text-yellow-400 fill-yellow-400" />
          <h3 className="text-sm font-medium text-text-secondary">Favorites</h3>
          <span className="text-xs text-text-secondary/60">({favorites.length})</span>
        </div>
        {favorites.length > 0 && (
          <button
            onClick={clearFavorites}
            className="flex items-center gap-1 text-xs text-text-secondary hover:text-red-400 transition-colors"
            title="Clear all favorites"
          >
            <Trash2 className="w-3 h-3" />
            Clear
          </button>
        )}
      </div>

      <div className="space-y-2">
        {visibleFavorites.map((fav) => (
          <div
            key={fav.file_path}
            className="group flex items-center justify-between p-3 bg-bg-secondary border border-border rounded-lg hover:border-accent/30 transition-colors cursor-pointer"
          >
            <button
              onClick={() => handleNoteClick(fav)}
              className="flex items-center gap-3 min-w-0 flex-1 text-left"
            >
              <FileText className="w-4 h-4 text-accent flex-shrink-0" />
              <div className="min-w-0">
                <p className="font-medium truncate">{fav.title}</p>
                <p className="text-xs text-text-secondary truncate">{fav.vault}</p>
              </div>
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation()
                removeFavorite(fav.file_path)
              }}
              className="p-1.5 rounded-lg text-text-secondary opacity-0 group-hover:opacity-100 hover:text-red-400 hover:bg-bg-tertiary transition-all"
              title="Remove from favorites"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      {favorites.length > maxVisible && (
        <p className="text-xs text-text-secondary mt-2 text-center">
          +{favorites.length - maxVisible} more favorites
        </p>
      )}
    </div>
  )
}
