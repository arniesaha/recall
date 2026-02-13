import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Brain, Zap, Clock, Tag } from 'lucide-react'
import SearchBar from '../components/SearchBar'

export default function Home() {
  const navigate = useNavigate()

  const handleSearch = (query, vault = 'work') => {
    navigate(`/search?q=${encodeURIComponent(query)}&vault=${vault}`)
  }

  const recentSearches = [
    'Action items from 1:1s',
    'Project timelines',
    'Meeting notes from last week'
  ]

  const quickFilters = [
    { label: 'Work', icon: Zap },
    { label: 'Personal', icon: Tag },
    { label: 'Recent', icon: Clock }
  ]

  return (
    <div className="max-w-2xl mx-auto px-4 py-12 md:py-24">
      {/* Hero */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-accent/10 mb-6">
          <Brain className="w-8 h-8 text-accent" />
        </div>
        <h1 className="text-3xl md:text-4xl font-bold mb-3">
          Search your knowledge
        </h1>
        <p className="text-text-secondary text-lg">
          Ask questions in natural language, get AI-powered answers from your notes.
        </p>
      </div>

      {/* Search bar */}
      <div className="mb-8">
        <SearchBar 
          onSearch={handleSearch} 
          autoFocus={true}
          size="large"
        />
      </div>

      {/* Recent searches */}
      <div className="mb-8">
        <h3 className="text-sm font-medium text-text-secondary mb-3">Try asking:</h3>
        <div className="flex flex-wrap gap-2">
          {recentSearches.map((search, idx) => (
            <button
              key={idx}
              onClick={() => handleSearch(search)}
              className="px-3 py-1.5 bg-bg-secondary border border-border rounded-lg text-sm text-text-secondary hover:text-text-primary hover:border-accent/30 transition-colors"
            >
              {search}
            </button>
          ))}
        </div>
      </div>

      {/* Quick filters */}
      <div>
        <h3 className="text-sm font-medium text-text-secondary mb-3">Quick filters:</h3>
        <div className="flex gap-2">
          {quickFilters.map((filter, idx) => (
            <button
              key={idx}
              onClick={() => handleSearch(`vault:${filter.label.toLowerCase()}`)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-bg-secondary border border-border rounded-lg text-sm hover:border-accent/30 transition-colors"
            >
              <filter.icon className="w-4 h-4 text-accent" />
              {filter.label}
            </button>
          ))}
        </div>
      </div>

      {/* Features hint */}
      <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
        {[
          { title: 'Semantic Search', desc: 'Find by meaning, not just keywords' },
          { title: 'AI Answers', desc: 'Get synthesized answers from your notes' },
          { title: 'Fast Results', desc: 'Instant search across all your knowledge' }
        ].map((feature, idx) => (
          <div key={idx} className="p-4">
            <h4 className="font-medium mb-1">{feature.title}</h4>
            <p className="text-sm text-text-secondary">{feature.desc}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
