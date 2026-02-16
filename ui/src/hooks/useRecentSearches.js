import { useState, useEffect } from 'react'

const STORAGE_KEY = 'recall-recent-searches'
const MAX_SEARCHES = 10

export function useRecentSearches() {
  const [recentSearches, setRecentSearches] = useState([])

  // Load on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        setRecentSearches(JSON.parse(stored))
      }
    } catch (e) {
      console.error('Failed to load recent searches:', e)
    }
  }, [])

  const addSearch = (query) => {
    if (!query?.trim()) return

    setRecentSearches(prev => {
      // Remove duplicate if exists
      const filtered = prev.filter(s => s.toLowerCase() !== query.toLowerCase())
      // Add to front, limit to max
      const updated = [query, ...filtered].slice(0, MAX_SEARCHES)
      
      // Persist
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
      } catch (e) {
        console.error('Failed to save recent searches:', e)
      }
      
      return updated
    })
  }

  const removeSearch = (query) => {
    setRecentSearches(prev => {
      const updated = prev.filter(s => s !== query)
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
      } catch (e) {
        console.error('Failed to save recent searches:', e)
      }
      return updated
    })
  }

  const clearSearches = () => {
    setRecentSearches([])
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch (e) {
      console.error('Failed to clear recent searches:', e)
    }
  }

  return { recentSearches, addSearch, removeSearch, clearSearches }
}
