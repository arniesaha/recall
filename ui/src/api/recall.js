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
 * @param {Object} options - Additional filters
 * @param {string} [options.person] - Optional person filter
 * @param {string} [options.vault] - Vault filter: "work", "personal", or "all" (default: "work")
 * @param {string} [options.dateFrom] - Date range start (YYYY-MM-DD)
 * @param {string} [options.dateTo] - Date range end (YYYY-MM-DD)
 * @returns {Promise<Array>} Search results
 */
export async function search(query, limit = 10, options = {}) {
  const { person = null, vault = 'work', dateFrom = null, dateTo = null } = options
  
  const body = { query, limit, vault }
  if (person) body.person = person
  if (dateFrom) body.date_from = dateFrom
  if (dateTo) body.date_to = dateTo
  
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

/**
 * Update note content
 * @param {string} path - Note path
 * @param {string} content - New content
 * @returns {Promise<Object>} Updated note
 */
export async function updateNote(path, content) {
  const response = await fetch(`${API_BASE}/notes/${encodeURIComponent(path)}`, {
    method: 'PUT',
    headers,
    body: JSON.stringify({ content })
  })

  if (!response.ok) {
    throw new Error(`Failed to update note: ${response.status}`)
  }

  return response.json()
}

/**
 * Create a new note
 * @param {string} title - Note title
 * @param {string} content - Note content (markdown)
 * @param {string} vault - Vault to create in ("work" or "personal")
 * @param {string} [folder] - Optional subfolder path
 * @returns {Promise<Object>} Created note info
 */
export async function createNote(title, content, vault = 'work', folder = null) {
  const body = { title, content, vault }
  if (folder) body.folder = folder

  const response = await fetch(`${API_BASE}/notes`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body)
  })

  if (!response.ok) {
    throw new Error(`Failed to create note: ${response.status}`)
  }

  return response.json()
}

/**
 * Get all tags across notes
 * @param {string} [vault] - Vault filter ("work", "personal", or "all")
 * @param {number} [limit] - Max tags to return
 * @returns {Promise<Object>} Tags with counts
 */
export async function getTags(vault = 'all', limit = 50) {
  const response = await fetch(`${API_BASE}/notes/tags?vault=${vault}&limit=${limit}`, {
    method: 'GET',
    headers
  })

  if (!response.ok) {
    throw new Error(`Failed to fetch tags: ${response.status}`)
  }

  return response.json()
}

/**
 * Get folders for a vault
 * @param {string} [vault] - Vault ("work" or "personal")
 * @returns {Promise<Object>} List of folder paths
 */
export async function getFolders(vault = 'work') {
  const response = await fetch(`${API_BASE}/notes/folders?vault=${vault}`, {
    method: 'GET',
    headers
  })

  if (!response.ok) {
    throw new Error(`Failed to fetch folders: ${response.status}`)
  }

  return response.json()
}

/**
 * Get recent notes
 * @param {number} [limit] - Max notes to return
 * @returns {Promise<Object>} Recent notes
 */
export async function getRecentNotes(limit = 10) {
  const response = await fetch(`${API_BASE}/notes/recent?limit=${limit}`, {
    method: 'GET',
    headers
  })

  if (!response.ok) {
    throw new Error(`Failed to fetch recent notes: ${response.status}`)
  }

  return response.json()
}
