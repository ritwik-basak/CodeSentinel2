import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * useSSEStream
 * Connects to a Server-Sent Events endpoint and accumulates events.
 *
 * Returns:
 *   events     — array of parsed JSON event objects received so far
 *   status     — 'idle' | 'connecting' | 'streaming' | 'complete' | 'error'
 *   report     — final report object (populated on type=complete)
 *   error      — error message string if status=error
 *   reconnect  — call to manually re-open the stream
 */
export function useSSEStream(url) {
  const [events, setEvents]   = useState([])
  const [status, setStatus]   = useState('idle')
  const [report, setReport]   = useState(null)
  const [error, setError]     = useState(null)

  const esRef      = useRef(null)
  const mountedRef = useRef(true)

  const connect = useCallback(() => {
    if (!url) return

    // Clean up any existing connection
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }

    setStatus('connecting')
    setEvents([])
    setReport(null)
    setError(null)

    const es = new EventSource(url)
    esRef.current = es

    es.onopen = () => {
      if (!mountedRef.current) return
      setStatus('streaming')
    }

    es.onmessage = (e) => {
      if (!mountedRef.current) return
      try {
        const evt = JSON.parse(e.data)
        setEvents(prev => [...prev, evt])

        if (evt.type === 'complete') {
          setReport(evt.report || {})
          setStatus('complete')
          es.close()
          esRef.current = null
        } else if (evt.type === 'error') {
          setError(evt.message || 'Unknown error')
          setStatus('error')
          es.close()
          esRef.current = null
        }
      } catch {
        // non-JSON frame, ignore
      }
    }

    es.onerror = () => {
      if (!mountedRef.current) return
      // Only treat as error if we haven't already finished
      setStatus(prev => {
        if (prev === 'complete') return prev
        setError('Connection lost. The stream disconnected.')
        return 'error'
      })
      es.close()
      esRef.current = null
    }
  }, [url])

  // Auto-connect when url changes
  useEffect(() => {
    mountedRef.current = true
    if (url) connect()
    return () => {
      mountedRef.current = false
      if (esRef.current) {
        esRef.current.close()
        esRef.current = null
      }
    }
  }, [url, connect])

  return { events, status, report, error, reconnect: connect }
}
