import { useState, useRef } from 'react'
import { Search, X, Loader2, Building2, User, Globe } from 'lucide-react'

const VAULT_OPTIONS = [
  { value: 'work', label: 'Work', icon: Building2, shortLabel: 'W' },
  { value: 'personal', label: 'Personal', icon: User, shortLabel: 'P' },
  { value: 'all', label: 'All', icon: Globe, shortLabel: 'A' },
]

export default function SearchBar({ 
  onSearch, 
  isLoading = false, 
  initialQuery = '',
  initialVault = 'work',
  autoFocus = false,
  size = 'large' // 'large' for home, 'normal' for results page
}) {
  const [value, setValue] = useState(initialQuery)
  const [vault, setVault] = useState(initialVault)
  const [showVaultMenu, setShowVaultMenu] = useState(false)
  const inputRef = useRef(null)

  const handleSubmit = (e) => {
    e.preventDefault()
    if (value.trim()) {
      onSearch(value.trim(), vault)
    }
  }
  
  const handleVaultChange = (newVault) => {
    setVault(newVault)
    setShowVaultMenu(false)
    // Re-run search if there's a query
    if (value.trim()) {
      onSearch(value.trim(), newVault)
    }
  }
  
  const currentVault = VAULT_OPTIONS.find(v => v.value === vault)

  const handleClear = () => {
    setValue('')
    inputRef.current?.focus()
  }

  const sizeClasses = size === 'large' 
    ? 'px-5 py-4 text-lg'
    : 'px-4 py-3 text-base'

  const iconSize = size === 'large' ? 'w-6 h-6' : 'w-5 h-5'

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div className={`
        relative flex items-center 
        bg-bg-secondary border border-border rounded-xl
        search-glow transition-all duration-200
        focus-within:border-accent/50
      `}>
        <div className={`pl-4 ${size === 'large' ? 'pl-5' : ''}`}>
          {isLoading ? (
            <Loader2 className={`${iconSize} text-text-secondary animate-spin`} />
          ) : (
            <Search className={`${iconSize} text-text-secondary`} />
          )}
        </div>

        <input
          ref={inputRef}
          id="search-input"
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Ask anything about your notes..."
          className={`
            flex-1 bg-transparent ${sizeClasses}
            placeholder:text-text-secondary/60
            focus:outline-none
          `}
          autoFocus={autoFocus}
          autoComplete="off"
        />

        {value && (
          <button
            type="button"
            onClick={handleClear}
            className="p-2 text-text-secondary hover:text-text-primary transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        )}

        {/* Vault selector */}
        <div className="relative pr-3">
          <button
            type="button"
            onClick={() => setShowVaultMenu(!showVaultMenu)}
            className={`
              flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg
              bg-bg-tertiary hover:bg-border
              text-text-secondary hover:text-text-primary
              text-sm font-medium transition-colors
              border border-transparent hover:border-border
            `}
            title={`Search in: ${currentVault?.label}`}
          >
            {currentVault && <currentVault.icon className="w-4 h-4" />}
            <span className="hidden sm:inline">{currentVault?.label}</span>
            <span className="sm:hidden">{currentVault?.shortLabel}</span>
          </button>
          
          {/* Dropdown menu */}
          {showVaultMenu && (
            <div className="absolute right-0 top-full mt-1 z-50 min-w-[140px] py-1 bg-bg-secondary border border-border rounded-lg shadow-xl">
              {VAULT_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => handleVaultChange(option.value)}
                  className={`
                    w-full flex items-center gap-2 px-3 py-2 text-sm
                    hover:bg-bg-tertiary transition-colors
                    ${vault === option.value ? 'text-accent' : 'text-text-primary'}
                  `}
                >
                  <option.icon className="w-4 h-4" />
                  <span>{option.label}</span>
                  {vault === option.value && (
                    <span className="ml-auto text-xs">✓</span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </form>
  )
}
