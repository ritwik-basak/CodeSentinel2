import axios from 'axios'
import { Loader2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const PILLS = [
  '4 Specialized AI Agents',
  'E2B Sandbox Verified',
  'Real-time Streaming',
]

export default function LandingPage() {
  const navigate              = useNavigate()
  const [url, setUrl]         = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    const trimmed = url.trim()
    if (!trimmed) {
      setError('Please enter a GitHub repository URL.')
      return
    }
    if (!trimmed.includes('github.com')) {
      setError('Please enter a valid GitHub URL (e.g. https://github.com/owner/repo).')
      return
    }

    setError('')
    setLoading(true)

    try {
      const base = import.meta.env.VITE_API_URL || ''
      const { data } = await axios.post(`${base}/review`, { repo_url: trimmed })
      navigate(`/review/${data.review_id}`)
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to start review.'
      setError(msg)
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        background: '#F8F6F0',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '48px 24px',
        opacity: 0,
        animation: 'fadeIn 0.3s ease forwards',
      }}
    >
      <style>{`
        @keyframes fadeIn { to { opacity: 1; } }
      `}</style>

      {/* Logo + wordmark */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '20px', marginBottom: '56px' }}>
        {/* Geometric sentinel logo — larger */}
        <svg width="72" height="72" viewBox="0 0 44 44" fill="none" xmlns="http://www.w3.org/2000/svg">
          {/* Outer shield */}
          <path d="M22 2L4 9v12c0 10.5 7.7 20.3 18 22.9C32.3 41.3 40 31.5 40 21V9L22 2z"
            fill="#111111" />
          {/* Inner accent */}
          <path d="M22 7L9 13v9c0 7.7 5.7 14.9 13 16.9C29.3 36.9 35 29.7 35 22v-9L22 7z"
            fill="#C9A227" opacity="0.18" />
          {/* Center scan line — top */}
          <rect x="14" y="17" width="16" height="2" rx="1" fill="#C9A227" />
          {/* Center scan line — mid */}
          <rect x="14" y="21" width="10" height="2" rx="1" fill="white" opacity="0.6" />
          {/* Center scan line — bot */}
          <rect x="14" y="25" width="13" height="2" rx="1" fill="white" opacity="0.35" />
          {/* Top-right dot accent */}
          <circle cx="33" cy="13" r="2.5" fill="#C9A227" />
        </svg>

        <div style={{ textAlign: 'center' }}>
          <div style={{
            fontFamily: "'Playfair Display', Georgia, serif",
            fontSize: '38px',
            fontWeight: 800,
            letterSpacing: '-0.02em',
            color: '#111111',
            lineHeight: 1.05,
          }}>
            CodeSentinel
          </div>
          <div style={{
            fontFamily: "'Inter', system-ui, sans-serif",
            fontSize: '13px',
            fontWeight: 500,
            color: '#888888',
            marginTop: '6px',
            letterSpacing: '0.01em',
          }}>
            Multi-Agent Code Analysis &amp; Self-Repair System
          </div>
        </div>
      </div>

      {/* Hero text */}
      <div style={{ textAlign: 'center', marginBottom: '52px', maxWidth: '640px' }}>
        <h1 style={{
          fontFamily: "'Playfair Display', Georgia, serif",
          fontSize: 'clamp(48px, 8vw, 72px)',
          fontWeight: 800,
          lineHeight: 1.08,
          letterSpacing: '-0.02em',
          color: '#111111',
          margin: '0 0 8px',
        }}>
          Analyze. Detect.
        </h1>
        <h1 style={{
          fontFamily: "'Playfair Display', Georgia, serif",
          fontSize: 'clamp(48px, 8vw, 72px)',
          fontWeight: 800,
          lineHeight: 1.08,
          letterSpacing: '-0.02em',
          color: '#C9A227',
          margin: '0 0 32px',
        }}>
          Auto-Repair.
        </h1>
        <p style={{
          fontFamily: "'Inter', system-ui, sans-serif",
          fontSize: '18px',
          fontWeight: 400,
          color: '#6B6B6B',
          lineHeight: 1.65,
          margin: 0,
        }}>
          Multi-agent AI that reviews your GitHub repository,
          <br />finds bugs, and fixes them automatically.
        </p>
      </div>

      {/* Input card */}
      <div style={{ width: '100%', maxWidth: '520px' }}>
        <form onSubmit={handleSubmit}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <input
              type="url"
              value={url}
              onChange={e => { setUrl(e.target.value); setError('') }}
              placeholder="https://github.com/owner/repository"
              disabled={loading}
              autoFocus
              style={{
                width: '100%',
                padding: '14px 18px',
                fontSize: '15px',
                fontFamily: "'Inter', system-ui, sans-serif",
                color: '#111111',
                background: '#FFFFFF',
                border: '1px solid #E0E0E0',
                borderRadius: '10px',
                outline: 'none',
                boxSizing: 'border-box',
                transition: 'box-shadow 0.15s ease, border-color 0.15s ease',
              }}
              onFocus={e => {
                e.target.style.borderColor = '#BBBBBB'
                e.target.style.boxShadow = '0 0 0 3px rgba(0,0,0,0.06)'
              }}
              onBlur={e => {
                e.target.style.borderColor = '#E0E0E0'
                e.target.style.boxShadow = 'none'
              }}
            />

            {error && (
              <p style={{
                fontFamily: "'Inter', sans-serif",
                fontSize: '13px',
                color: '#CC3333',
                margin: '0',
                paddingLeft: '4px',
              }}>
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%',
                padding: '14px 24px',
                fontSize: '15px',
                fontWeight: 600,
                fontFamily: "'Inter', system-ui, sans-serif",
                color: '#FFFFFF',
                background: loading ? '#444444' : '#111111',
                border: 'none',
                borderRadius: '10px',
                cursor: loading ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                transition: 'background 0.15s ease',
              }}
              onMouseEnter={e => { if (!loading) e.currentTarget.style.background = '#333333' }}
              onMouseLeave={e => { if (!loading) e.currentTarget.style.background = '#111111' }}
            >
              {loading ? (
                <>
                  <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
                  Starting analysis…
                </>
              ) : (
                'Analyze Repository →'
              )}
            </button>
          </div>
        </form>

        {/* Stat pills */}
        <div style={{
          marginTop: '32px',
          display: 'flex',
          justifyContent: 'center',
          gap: '10px',
          flexWrap: 'wrap',
        }}>
          {PILLS.map((pill) => (
            <span
              key={pill}
              style={{
                fontFamily: "'Inter', sans-serif",
                fontSize: '12px',
                fontWeight: 500,
                color: '#555555',
                background: '#FFFFFF',
                border: '1px solid #E0E0E0',
                borderRadius: '20px',
                padding: '6px 14px',
              }}
            >
              {pill}
            </span>
          ))}
        </div>
      </div>

      {/* Footer */}
      <p style={{
        marginTop: '64px',
        fontFamily: "'Inter', sans-serif",
        fontSize: '11px',
        fontWeight: 500,
        color: '#BBBBBB',
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        textAlign: 'center',
      }}>
        Powered by LangGraph · Groq · Pinecone · E2B
      </p>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}
