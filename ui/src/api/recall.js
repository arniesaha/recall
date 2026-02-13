// API configuration
const API_BASE = import.meta.env.VITE_API_URL || '/api'
const API_TOKEN = import.meta.env.VITE_API_TOKEN || '7a2953e9c597afe9c3f16c5b58a3c0eeba87cdb311a46103'

const headers = {
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${API_TOKEN}`
}

/**
 * Semantic search across notes
 * @param {string} query - Search query
 * @param {number} limit - Max results (default 10)
 * @param {string} [person] - Optional person filter
 * @param {string} [vault] - Vault filter: "work", "personal", or "all" (default: "work")
 * @returns {Promise<Array>} Search results
 */
export async function search(query, limit = 10, person = null, vault = 'work') {
  const body = { query, limit, vault }
  if (person) {
    body.person = person
  }
  
  const response = await fetch(`${API_BASE}/search`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body)
  })

  if (!response.ok) {
    throw new Error(`Search failed: ${response.status}`)
  }

  const data = await response.json()
  return data.results || []
}

/**
 * RAG query with AI-generated answer
 * @param {string} query - Natural language question
 * @param {number} limit - Max context chunks (default 5)
 * @param {string} [vault] - Vault filter: "work", "personal", or "all" (default: "work")
 * @returns {Promise<Object>} AI answer and sources
 */
export async function queryRAG(query, limit = 5, vault = 'work') {
  const response = await fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ question: query, limit, vault })
  })

  if (!response.ok) {
    throw new Error(`Query failed: ${response.status}`)
  }

  return response.json()
}

/**
 * Get note content by path
 * @param {string} path - Note path (e.g., "work/people/sameer/2026-01-28.md")
 * @returns {Promise<Object>} Note content and metadata
 */
export async function getNote(path) {
  const response = await fetch(`${API_BASE}/notes/${encodeURIComponent(path)}`, {
    method: 'GET',
    headers
  })

  if (!response.ok) {
    throw new Error(`Failed to fetch note: ${response.status}`)
  }

  return response.json()
}

/**
 * Get the full notes tree structure
 * @returns {Promise<Object>} Tree structure with folders and files
 */
export async function getNotesTree() {
  const response = await fetch(`${API_BASE}/notes/tree`, {
    method: 'GET',
    headers
  })

  if (!response.ok) {
    throw new Error(`Failed to fetch tree: ${response.status}`)
  }

  return response.json()
}
