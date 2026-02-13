/**
 * Utility functions for detecting person-related queries
 */

// Patterns that indicate a person-related query
const PERSON_PATTERNS = [
  // "1:1 with X", "1-1 with X", "one on one with X"
  /(?:1[:\-]1|one[\s-]?on[\s-]?one)\s+(?:with|meeting)\s+(\w+)/i,
  // "meeting with X", "call with X", "sync with X"
  /(?:meeting|call|sync|chat|discussion)\s+with\s+(\w+)/i,
  // "prep for X", "prepare for X" (when followed by name-like word)
  /(?:prep|prepare|preparing)\s+(?:for\s+)?(?:1[:\-]1\s+)?(?:with\s+)?(\w+)/i,
  // "X's notes", "X notes", "notes on X", "notes about X"
  /(\w+)(?:'s)?\s+notes?\b/i,
  /notes?\s+(?:on|about|for|with)\s+(\w+)/i,
  // "about X", "regarding X" (at end of query)
  /(?:about|regarding|re:?)\s+(\w+)\s*$/i,
  // "feedback from X", "update from X"
  /(?:feedback|update|updates|info|information)\s+(?:from|about|on)\s+(\w+)/i,
  // "X feedback", "X project"
  /(\w+)\s+(?:feedback|project|status|update)/i,
]

// Common words that are NOT person names (filter these out)
const NON_PERSON_WORDS = new Set([
  'the', 'a', 'an', 'my', 'our', 'their', 'his', 'her', 'its',
  'this', 'that', 'these', 'those', 'all', 'some', 'any',
  'meeting', 'meetings', 'call', 'calls', 'sync', 'syncs',
  'notes', 'note', 'document', 'documents', 'file', 'files',
  'today', 'tomorrow', 'yesterday', 'week', 'month', 'year',
  'work', 'project', 'projects', 'team', 'teams', 'company',
  'recent', 'latest', 'last', 'next', 'upcoming', 'past',
  'important', 'urgent', 'follow', 'up', 'action', 'items',
  'summary', 'summaries', 'overview', 'status', 'update', 'updates',
  'prep', 'prepare', 'preparing', 'preparation',
])

/**
 * Detects if a query is person-related and extracts the person name
 * @param {string} query - Search query
 * @returns {{ isPerson: boolean, personName: string | null, confidence: 'high' | 'medium' | 'low' }}
 */
export function detectPersonQuery(query) {
  if (!query || typeof query !== 'string') {
    return { isPerson: false, personName: null, confidence: 'low' }
  }

  const normalizedQuery = query.trim().toLowerCase()
  
  for (const pattern of PERSON_PATTERNS) {
    const match = query.match(pattern)
    if (match && match[1]) {
      const potentialName = match[1].trim()
      
      // Filter out non-person words
      if (NON_PERSON_WORDS.has(potentialName.toLowerCase())) {
        continue
      }
      
      // Names are typically 2+ characters and start with a letter
      if (potentialName.length < 2 || !/^[a-zA-Z]/.test(potentialName)) {
        continue
      }
      
      // Capitalize first letter for display
      const personName = potentialName.charAt(0).toUpperCase() + potentialName.slice(1).toLowerCase()
      
      // High confidence for explicit patterns
      const highConfidencePatterns = [/1[:\-]1/, /meeting\s+with/i, /call\s+with/i]
      const confidence = highConfidencePatterns.some(p => p.test(query)) ? 'high' : 'medium'
      
      return { isPerson: true, personName, confidence }
    }
  }

  return { isPerson: false, personName: null, confidence: 'low' }
}

/**
 * Extract person name from a file path
 * @param {string} filePath - File path like "work/people/nikhil/2026-01-28.md"
 * @returns {string | null} Person name or null
 */
export function extractPersonFromPath(filePath) {
  if (!filePath) return null
  
  // Common patterns: people/name/, person/name/, 1-1/name/
  const patterns = [
    /people\/([^/]+)\//i,
    /person\/([^/]+)\//i,
    /1[-:]?1s?\/([^/]+)\//i,
    /meetings\/([^/]+)\//i,
  ]
  
  for (const pattern of patterns) {
    const match = filePath.match(pattern)
    if (match && match[1]) {
      const name = match[1]
      // Skip if it looks like a date or common folder name
      if (/^\d{4}/.test(name) || ['notes', 'archive', 'templates'].includes(name.toLowerCase())) {
        continue
      }
      return name.charAt(0).toUpperCase() + name.slice(1).toLowerCase()
    }
  }
  
  return null
}

/**
 * Get browse path for a person
 * @param {string} personName - Person's name
 * @returns {string} Path to browse their notes
 */
export function getPersonBrowsePath(personName) {
  if (!personName) return '/browse'
  // Return path that can be used with the FileTree
  return `/browse?person=${encodeURIComponent(personName.toLowerCase())}`
}

/**
 * Generate helpful message when no results found for a person query
 * @param {string} personName - Person's name
 * @returns {string} Helpful markdown message
 */
export function getNoResultsMessage(personName) {
  if (!personName) {
    return "I couldn't find any relevant notes for your query."
  }
  
  return `I couldn't find indexed notes mentioning **${personName}**. Their notes might not be in the search index yet.

**Try browsing directly:**
- Go to Browse → people → ${personName.toLowerCase()}
- Or check if notes exist under a different folder structure`
}
