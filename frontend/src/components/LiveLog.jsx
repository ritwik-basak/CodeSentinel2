import { AnimatePresence, motion } from 'framer-motion'
import { Terminal } from 'lucide-react'
import { useEffect, useRef } from 'react'

function stepColor(step) {
  const map = {
    fetch:       '#818CF8',
    parse:       '#A78BFA',
    embed:       '#C084FC',
    store:       '#E879F9',
    orchestrate: '#60A5FA',
    plan:        '#34D399',
    bug_detect:  '#F87171',
    fix:         '#FB923C',
    security:    '#FBBF24',
    doc_check:   '#A3E635',
    quality:     '#2DD4BF',
    synthesize:  '#818CF8',
  }
  return map[step] || '#9CA3AF'
}

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export default function LiveLog({ events }) {
  const bottomRef = useRef(null)

  // Auto-scroll to bottom whenever a new event comes in
  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [events])

  return (
    <div className="glass-card p-0 overflow-hidden">
      {/* Terminal header bar */}
      <div className="flex items-center gap-2 px-4 py-3 bg-[#0F0F23] border-b border-[#1E1E3F]">
        <div className="flex gap-1.5">
          <div className="w-3 h-3 rounded-full bg-[#FF5F57]" />
          <div className="w-3 h-3 rounded-full bg-[#FFBD2E]" />
          <div className="w-3 h-3 rounded-full bg-[#28C840]" />
        </div>
        <Terminal className="w-3.5 h-3.5 text-gray-500 ml-2" />
        <span className="text-gray-500 text-xs font-mono">live-output</span>
      </div>

      {/* Log body */}
      <div
        className="terminal-log bg-[#0F0F23] h-64 overflow-y-auto p-4 font-mono text-xs"
        style={{ minHeight: '16rem' }}
      >
        {events.length === 0 ? (
          <div className="text-gray-600 italic">Waiting for pipeline to start…</div>
        ) : (
          <AnimatePresence initial={false}>
            {events.map((evt, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
                className="flex items-start gap-2 mb-1.5 leading-relaxed"
              >
                {/* Timestamp */}
                <span className="text-[#3D3D6B] flex-shrink-0 tabular-nums">
                  {formatTime(evt.timestamp)}
                </span>

                {/* Step pill */}
                <span
                  className="flex-shrink-0 font-semibold uppercase"
                  style={{ color: stepColor(evt.step), minWidth: '90px' }}
                >
                  [{evt.step || evt.type}]
                </span>

                {/* Message */}
                <span className={`
                  ${evt.type === 'error'   ? 'text-red-400'
                    : evt.status === 'skipped' ? 'text-amber-400'
                    : 'text-[#A0F0B0]'}
                `}>
                  {evt.message}
                </span>
              </motion.div>
            ))}
          </AnimatePresence>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
