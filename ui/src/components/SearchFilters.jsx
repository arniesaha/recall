import { useState } from 'react'
import { Calendar, User, ChevronDown, X, Filter } from 'lucide-react'

const DATE_PRESETS = [
  { label: 'Today', value: 'today' },
  { label: 'This week', value: 'this_week' },
  { label: 'This month', value: 'this_month' },
  { label: 'Last 3 months', value: 'last_3_months' },
  { label: 'Custom range', value: 'custom' },
]

export default function SearchFilters({ 
  onFilterChange,
  dateFilter,
  personFilter,
  dateFrom,
  dateTo,
}) {
  const [showDateMenu, setShowDateMenu] = useState(false)
  const [showPersonInput, setShowPersonInput] = useState(false)
  const [customDateFrom, setCustomDateFrom] = useState(dateFrom || '')
  const [customDateTo, setCustomDateTo] = useState(dateTo || '')
  const [personInput, setPersonInput] = useState(personFilter || '')

  const hasActiveFilters = dateFilter || personFilter

  const handleDatePreset = (preset) => {
    if (preset === 'custom') {
      // Keep menu open for custom date input
      return
    }
    
    const now = new Date()
    let from, to
    
    switch (preset) {
      case 'today':
        from = to = now.toISOString().split('T')[0]
        break
      case 'this_week':
        const startOfWeek = new Date(now)
        startOfWeek.setDate(now.getDate() - now.getDay())
        from = startOfWeek.toISOString().split('T')[0]
        to = now.toISOString().split('T')[0]
        break
      case 'this_month':
        from = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`
        to = now.toISOString().split('T')[0]
        break
      case 'last_3_months':
        const threeMonthsAgo = new Date(now)
        threeMonthsAgo.setMonth(now.getMonth() - 3)
        from = threeMonthsAgo.toISOString().split('T')[0]
        to = now.toISOString().split('T')[0]
        break
      default:
        from = to = null
    }
    
    onFilterChange({ dateFilter: preset, dateFrom: from, dateTo: to })
    setShowDateMenu(false)
  }

  const handleCustomDateApply = () => {
    if (customDateFrom || customDateTo) {
      onFilterChange({ 
        dateFilter: 'custom', 
        dateFrom: customDateFrom, 
        dateTo: customDateTo 
      })
    }
    setShowDateMenu(false)
  }

  const handlePersonApply = () => {
    if (personInput.trim()) {
      onFilterChange({ personFilter: personInput.trim() })
    }
    setShowPersonInput(false)
  }

  const clearDateFilter = () => {
    onFilterChange({ dateFilter: null, dateFrom: null, dateTo: null })
    setCustomDateFrom('')
    setCustomDateTo('')
  }

  const clearPersonFilter = () => {
    onFilterChange({ personFilter: null })
    setPersonInput('')
  }

  const getDateLabel = () => {
    if (!dateFilter) return 'Date'
    const preset = DATE_PRESETS.find(p => p.value === dateFilter)
    if (preset && dateFilter !== 'custom') return preset.label
    if (dateFrom && dateTo && dateFrom === dateTo) return dateFrom
    if (dateFrom && dateTo) return `${dateFrom} - ${dateTo}`
    if (dateFrom) return `From ${dateFrom}`
    if (dateTo) return `Until ${dateTo}`
    return 'Date'
  }

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {/* Filter icon indicator */}
      {hasActiveFilters && (
        <div className="flex items-center gap-1 text-accent text-sm">
          <Filter className="w-4 h-4" />
          <span>Filtered</span>
        </div>
      )}

      {/* Date filter */}
      <div className="relative">
        <button
          onClick={() => setShowDateMenu(!showDateMenu)}
          className={`
            flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm
            border transition-colors
            ${dateFilter 
              ? 'bg-accent/10 border-accent/30 text-accent' 
              : 'bg-bg-secondary border-border text-text-secondary hover:text-text-primary hover:border-accent/30'
            }
          `}
        >
          <Calendar className="w-4 h-4" />
          <span>{getDateLabel()}</span>
          {dateFilter ? (
            <button
              onClick={(e) => {
                e.stopPropagation()
                clearDateFilter()
              }}
              className="hover:text-red-400 ml-1"
            >
              <X className="w-3 h-3" />
            </button>
          ) : (
            <ChevronDown className="w-3 h-3" />
          )}
        </button>

        {showDateMenu && (
          <div className="absolute left-0 top-full mt-1 z-50 min-w-[200px] py-1 bg-bg-secondary border border-border rounded-lg shadow-xl">
            {DATE_PRESETS.map((preset) => (
              <button
                key={preset.value}
                onClick={() => handleDatePreset(preset.value)}
                className={`
                  w-full px-3 py-2 text-sm text-left
                  hover:bg-bg-tertiary transition-colors
                  ${dateFilter === preset.value ? 'text-accent' : 'text-text-primary'}
                `}
              >
                {preset.label}
              </button>
            ))}
            
            {/* Custom date inputs */}
            <div className="border-t border-border mt-1 pt-2 px-3 pb-2">
              <div className="space-y-2">
                <input
                  type="date"
                  value={customDateFrom}
                  onChange={(e) => setCustomDateFrom(e.target.value)}
                  className="w-full px-2 py-1 text-sm bg-bg-tertiary border border-border rounded focus:outline-none focus:border-accent/50"
                  placeholder="From"
                />
                <input
                  type="date"
                  value={customDateTo}
                  onChange={(e) => setCustomDateTo(e.target.value)}
                  className="w-full px-2 py-1 text-sm bg-bg-tertiary border border-border rounded focus:outline-none focus:border-accent/50"
                  placeholder="To"
                />
                <button
                  onClick={handleCustomDateApply}
                  className="w-full px-2 py-1 text-sm bg-accent hover:bg-accent-muted text-white rounded transition-colors"
                >
                  Apply
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Person filter */}
      <div className="relative">
        {showPersonInput ? (
          <div className="flex items-center gap-1">
            <input
              type="text"
              value={personInput}
              onChange={(e) => setPersonInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handlePersonApply()}
              placeholder="Enter name..."
              className="px-3 py-1.5 text-sm bg-bg-secondary border border-accent/50 rounded-lg focus:outline-none w-32"
              autoFocus
            />
            <button
              onClick={handlePersonApply}
              className="px-2 py-1.5 text-sm bg-accent hover:bg-accent-muted text-white rounded-lg transition-colors"
            >
              Apply
            </button>
            <button
              onClick={() => {
                setShowPersonInput(false)
                setPersonInput('')
              }}
              className="p-1.5 text-text-secondary hover:text-text-primary"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <button
            onClick={() => setShowPersonInput(true)}
            className={`
              flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm
              border transition-colors
              ${personFilter 
                ? 'bg-accent/10 border-accent/30 text-accent' 
                : 'bg-bg-secondary border-border text-text-secondary hover:text-text-primary hover:border-accent/30'
              }
            `}
          >
            <User className="w-4 h-4" />
            <span>{personFilter || 'Person'}</span>
            {personFilter && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  clearPersonFilter()
                }}
                className="hover:text-red-400 ml-1"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </button>
        )}
      </div>
    </div>
  )
}
