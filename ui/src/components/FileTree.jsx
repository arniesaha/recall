import { useState, useEffect } from 'react'
import { Folder, FolderOpen, FileText, ChevronRight, ChevronDown } from 'lucide-react'

const STORAGE_KEY = 'recall-expanded-folders'

/**
 * Load expanded state from localStorage
 */
function loadExpandedState() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved ? JSON.parse(saved) : {}
  } catch {
    return {}
  }
}

/**
 * Save expanded state to localStorage
 */
function saveExpandedState(state) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    // Ignore storage errors
  }
}

/**
 * Count files in a tree node recursively
 */
function countFiles(node) {
  if (!node || typeof node !== 'object') return 0
  if (Array.isArray(node)) return node.length
  
  return Object.entries(node).reduce((sum, [key, child]) => {
    // Skip the _files_ key name, just count its contents
    if (Array.isArray(child)) return sum + child.length
    if (typeof child === 'object') return sum + countFiles(child)
    return sum
  }, 0)
}

/**
 * FileTreeNode - Renders a single folder or file
 */
function FileTreeNode({ 
  name, 
  node, 
  path, 
  expanded, 
  onToggle, 
  onFileClick, 
  selectedFile,
  depth = 0 
}) {
  const isFolder = node && typeof node === 'object' && !Array.isArray(node)
  const isFileList = Array.isArray(node)
  const isExpanded = expanded[path] ?? false
  const fileCount = isFolder || isFileList ? countFiles(node) : 0
  
  const indent = depth * 16

  if (isFolder) {
    // Render folder with children
    const children = Object.entries(node).sort(([a], [b]) => {
      // Folders first, then files
      const aIsFolder = typeof node[a] === 'object' && !Array.isArray(node[a])
      const bIsFolder = typeof node[b] === 'object' && !Array.isArray(node[b])
      if (aIsFolder && !bIsFolder) return -1
      if (!aIsFolder && bIsFolder) return 1
      return a.localeCompare(b)
    })

    return (
      <div className="select-none">
        <button
          onClick={() => onToggle(path)}
          className={`
            w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left
            hover:bg-bg-tertiary transition-colors group
            ${isExpanded ? 'text-text-primary' : 'text-text-secondary'}
          `}
          style={{ paddingLeft: `${12 + indent}px` }}
        >
          <span className="text-text-secondary group-hover:text-text-primary transition-colors">
            {isExpanded ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
          </span>
          {isExpanded ? (
            <FolderOpen className="w-4 h-4 text-accent" />
          ) : (
            <Folder className="w-4 h-4 text-accent" />
          )}
          <span className="flex-1 truncate font-medium">{name}</span>
          <span className="text-xs text-text-secondary opacity-60">
            {fileCount} {fileCount === 1 ? 'file' : 'files'}
          </span>
        </button>
        
        {isExpanded && (
          <div className="animate-slide-down">
            {children.map(([childName, childNode]) => (
              <FileTreeNode
                key={childName}
                name={childName}
                node={childNode}
                path={`${path}/${childName}`}
                expanded={expanded}
                onToggle={onToggle}
                onFileClick={onFileClick}
                selectedFile={selectedFile}
                depth={depth + 1}
              />
            ))}
          </div>
        )}
      </div>
    )
  }

  if (isFileList) {
    // Render folder containing file array
    return (
      <div className="select-none">
        <button
          onClick={() => onToggle(path)}
          className={`
            w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left
            hover:bg-bg-tertiary transition-colors group
            ${isExpanded ? 'text-text-primary' : 'text-text-secondary'}
          `}
          style={{ paddingLeft: `${12 + indent}px` }}
        >
          <span className="text-text-secondary group-hover:text-text-primary transition-colors">
            {isExpanded ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
          </span>
          {isExpanded ? (
            <FolderOpen className="w-4 h-4 text-accent" />
          ) : (
            <Folder className="w-4 h-4 text-accent" />
          )}
          <span className="flex-1 truncate font-medium">{name}</span>
          <span className="text-xs text-text-secondary opacity-60">
            {fileCount} {fileCount === 1 ? 'file' : 'files'}
          </span>
        </button>
        
        {isExpanded && (
          <div className="animate-slide-down">
            {node
              .slice() // Create copy to avoid mutating
              .sort((a, b) => {
                // Handle both object format {name, path} and string format
                const nameA = typeof a === 'object' ? a.name : a
                const nameB = typeof b === 'object' ? b.name : b
                return nameA.localeCompare(nameB)
              })
              .map((file) => {
                // Handle both object format {name, path} and string format
                const fileName = typeof file === 'object' ? file.name : file
                const filePath = typeof file === 'object' ? file.path : `${path}/${fileName}`
                const isSelected = selectedFile === filePath
                const displayName = fileName.replace(/\.[^.]+$/, '')
                
                return (
                  <button
                    key={filePath}
                    onClick={() => onFileClick(filePath)}
                    className={`
                      w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left
                      transition-colors
                      ${isSelected 
                        ? 'bg-accent/20 text-accent' 
                        : 'text-text-secondary hover:bg-bg-tertiary hover:text-text-primary'}
                    `}
                    style={{ paddingLeft: `${12 + indent + 16}px` }}
                  >
                    <FileText className={`w-4 h-4 flex-shrink-0 ${isSelected ? 'text-accent' : ''}`} />
                    <span className="truncate">{displayName}</span>
                  </button>
                )
              })}
          </div>
        )}
      </div>
    )
  }

  // Single file (shouldn't happen in typical tree structure)
  return null
}

/**
 * FileTree - Main component that renders the full tree
 */
export default function FileTree({ tree, onFileClick, selectedFile, expandPath = null }) {
  const [expanded, setExpanded] = useState(() => loadExpandedState())
  const [expandedFromProp, setExpandedFromProp] = useState(false)

  // Auto-expand path from prop (e.g., from URL query param)
  useEffect(() => {
    if (expandPath && tree && !expandedFromProp) {
      // Expand all folders in the path
      const pathParts = expandPath.split('/')
      const newExpanded = { ...expanded }
      let currentPath = ''
      
      for (const part of pathParts) {
        currentPath = currentPath ? `${currentPath}/${part}` : part
        newExpanded[currentPath] = true
      }
      
      setExpanded(newExpanded)
      setExpandedFromProp(true)
    }
  }, [expandPath, tree, expandedFromProp])

  // Save expanded state when it changes
  useEffect(() => {
    saveExpandedState(expanded)
  }, [expanded])

  const handleToggle = (path) => {
    setExpanded(prev => ({
      ...prev,
      [path]: !prev[path]
    }))
  }

  if (!tree || Object.keys(tree).length === 0) {
    return (
      <div className="text-center py-8 text-text-secondary">
        No files found
      </div>
    )
  }

  // Sort root folders
  const rootEntries = Object.entries(tree).sort(([a], [b]) => a.localeCompare(b))

  return (
    <div className="space-y-1">
      {rootEntries.map(([name, node]) => (
        <FileTreeNode
          key={name}
          name={name}
          node={node}
          path={name}
          expanded={expanded}
          onToggle={handleToggle}
          onFileClick={onFileClick}
          selectedFile={selectedFile}
          depth={0}
        />
      ))}
    </div>
  )
}
