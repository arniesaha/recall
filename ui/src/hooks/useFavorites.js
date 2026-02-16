import { useState, useEffect, useCallback } from 'react'

const STORAGE_KEY = 'recall-favorites'

/**
 * Hook for managing favorite/bookmarked notes
 * Persists to localStorage
 */
export function useFavorites() {
  const [favorites, setFavorites] = useState([])

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        // Validate structure
        if (Array.isArray(parsed)) {
          setFavorites(parsed)
        }
      }
    } catch (err) {
      console.error('Failed to load favorites:', err)
    }
  }, [])

  // Save to localStorage whenever favorites change
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(favorites))
    } catch (err) {
      console.error('Failed to save favorites:', err)
    }
  }, [favorites])

  /**
   * Add a note to favorites
   * @param {Object} note - Note object with at least { file_path, title, vault }
   */
  const addFavorite = useCallback((note) => {
    if (!note?.file_path) return

    setFavorites(prev => {
      // Check if already favorited
      if (prev.some(f => f.file_path === note.file_path)) {
        return prev
      }
      
      return [...prev, {
        file_path: note.file_path,
        title: note.title || note.file_path.split('/').pop()?.replace(/\.[^.]+$/, '') || 'Untitled',
        vault: note.vault || 'work',
        addedAt: new Date().toISOString()
      }]
    })
  }, [])

  /**
   * Remove a note from favorites
   * @param {string} filePath - The file path to remove
   */
  const removeFavorite = useCallback((filePath) => {
    setFavorites(prev => prev.filter(f => f.file_path !== filePath))
  }, [])

  /**
   * Toggle favorite status
   * @param {Object} note - Note object
   * @returns {boolean} New favorite status
   */
  const toggleFavorite = useCallback((note) => {
    if (!note?.file_path) return false

    const isFav = favorites.some(f => f.file_path === note.file_path)
    if (isFav) {
      removeFavorite(note.file_path)
      return false
    } else {
      addFavorite(note)
      return true
    }
  }, [favorites, addFavorite, removeFavorite])

  /**
   * Check if a note is favorited
   * @param {string} filePath - The file path to check
   * @returns {boolean}
   */
  const isFavorite = useCallback((filePath) => {
    return favorites.some(f => f.file_path === filePath)
  }, [favorites])

  /**
   * Clear all favorites
   */
  const clearFavorites = useCallback(() => {
    setFavorites([])
  }, [])

  return {
    favorites,
    addFavorite,
    removeFavorite,
    toggleFavorite,
    isFavorite,
    clearFavorites
  }
}
