import { useState, useCallback } from 'react'
import { search, queryRAG } from '../api/recall'
import { detectPersonQuery, getNoResultsMessage } from '../utils/personDetection'

/**
 * Hook for managing search state and API calls
 */
export function useSearch() {
  const [query, setQuery] = useState('')
  const [vault, setVault] = useState('work')
  const [results, setResults] = useState([])
  const [aiAnswer, setAiAnswer] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isAiLoading, setIsAiLoading] = useState(false)
  const [error, setError] = useState(null)
  const [detectedPerson, setDetectedPerson] = useState(null)

  const performSearch = useCallback(async (searchQuery, vaultFilter = 'work', personFilter = null) => {
    if (!searchQuery.trim()) {
      setResults([])
      setAiAnswer(null)
      setDetectedPerson(null)
      return
    }

    setQuery(searchQuery)
    setVault(vaultFilter)
    setIsLoading(true)
    setIsAiLoading(true)
    setError(null)

    // Detect if this is a person-related query
    const personDetection = detectPersonQuery(searchQuery)
    const effectivePerson = personFilter || (personDetection.isPerson ? personDetection.personName : null)
    setDetectedPerson(personDetection.isPerson ? personDetection.personName : null)

    try {
      // Run search and RAG query in parallel
      const [searchResults, ragResponse] = await Promise.all([
        search(searchQuery, 10, effectivePerson, vaultFilter),
        queryRAG(searchQuery, 5, vaultFilter)
      ])

      setResults(searchResults)
      setIsLoading(false)

      // Enhance AI answer with helpful fallback if no results for person query
      if (personDetection.isPerson && searchResults.length === 0 && ragResponse) {
        const noResultsHint = getNoResultsMessage(personDetection.personName)
        // Check if AI answer indicates no results found
        const answerLower = (ragResponse.answer || '').toLowerCase()
        const indicatesNoResults = 
          answerLower.includes("couldn't find") ||
          answerLower.includes("no information") ||
          answerLower.includes("don't have") ||
          answerLower.includes("unable to find") ||
          answerLower.includes("no notes") ||
          answerLower.includes("no relevant")
        
        if (indicatesNoResults || !ragResponse.answer) {
          setAiAnswer({
            ...ragResponse,
            answer: ragResponse.answer 
              ? `${ragResponse.answer}\n\n---\n\n${noResultsHint}`
              : noResultsHint,
            detectedPerson: personDetection.personName,
            hasNoResults: true
          })
        } else {
          setAiAnswer({ ...ragResponse, detectedPerson: personDetection.personName })
        }
      } else {
        setAiAnswer(ragResponse ? { ...ragResponse, detectedPerson: personDetection.isPerson ? personDetection.personName : null } : null)
      }
      setIsAiLoading(false)
    } catch (err) {
      console.error('Search error:', err)
      setError(err.message)
      setIsLoading(false)
      setIsAiLoading(false)
    }
  }, [])

  const clearSearch = useCallback(() => {
    setQuery('')
    setResults([])
    setAiAnswer(null)
    setError(null)
    setDetectedPerson(null)
  }, [])

  return {
    query,
    vault,
    results,
    aiAnswer,
    isLoading,
    isAiLoading,
    error,
    detectedPerson,
    performSearch,
    clearSearch
  }
}
