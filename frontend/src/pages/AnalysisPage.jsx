import { motion } from 'framer-motion'
import { AlertTriangle, ArrowLeft, RefreshCw } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import AgentTimeline from '../components/AgentTimeline'
import LiveLog from '../components/LiveLog'
import StatCards from '../components/StatCards'
import { useSSEStream } from '../hooks/useSSEStream'
import ResultsPage from './ResultsPage'

// Map event step names → agent timeline keys
const STEP_MAP = {
  fetch:       'fetch',
  parse:       'parse',
  embed:       'embed',
  store:       'store',
  orchestrate: 'orchestrate',
  plan:        'plan',
  bug_detect:  'bug_detect',
  fix:         'fix',
  security:    'security',
  doc_check:   'doc_check',
  quality:     'quality',
  synthesize:  'synthesize',
}

function buildAgentStatuses(events) {
  const statuses = {}

  for (const evt of events) {
    if (evt.type !== 'progress') continue
    const key = STEP_MAP[evt.step]
    if (!key) continue

    statuses[key] = {
      status:  evt.status === 'complete' ? 'complete'
               : evt.status === 'skipped' ? 'skipped'
               : evt.status === 'error'   ? 'error'
               : 'complete',
      message: evt.message,
    }
  }

  return statuses
}

function extractStats(events, report) {
  const stats = {}

  // Files & functions from parse event
  for (const evt of events) {
    if (evt.step === 'parse' && evt.message) {
      const mFiles = evt.message.match(/Parsed (\d+) files/)
      const mFuncs = evt.message.match(/found (\d+) functions/)
      if (mFiles) stats.files     = parseInt(mFiles[1])
      if (mFuncs) stats.functions = parseInt(mFuncs[1])
    }
    if (evt.step === 'bug_detect' && evt.message) {
      const m = evt.message.match(/(\d+) bug/)
      if (m) stats.bugs = parseInt(m[1])
    }
    if (evt.step === 'synthesize' && evt.message) {
      const m = evt.message.match(/\((\d+)\/100\)/)
      if (m) stats.health = parseInt(m[1])
    }
  }

  // Prefer report data if available
  if (report) {
    const sum = report.summary || {}
    if (sum.total_files     != null) stats.files     = sum.total_files
    if (sum.total_functions != null) stats.functions = sum.total_functions
    if (sum.health_score    != null) stats.health    = sum.health_score
    if (report.bugs)                 stats.bugs       = report.bugs.length
  }

  return stats
}

function determineRunningStep(events) {
  // The step currently running is the one that is the latest not yet complete/skipped
  // We use a simple heuristic: the step after the last completed step
  const ORDER = ['fetch','parse','embed','store','orchestrate','plan','bug_detect','fix','security','doc_check','quality','synthesize']
  const done  = new Set()

  for (const evt of events) {
    if (evt.type === 'progress' && (evt.status === 'complete' || evt.status === 'skipped')) {
      done.add(evt.step)
    }
  }

  for (const step of ORDER) {
    if (!done.has(step)) return step
  }
  return null
}

export default function AnalysisPage() {
  const { jobId }  = useParams()
  const navigate   = useNavigate()
  const sseUrl     = jobId ? `/review/${jobId}/stream` : null

  const { events, status, report, error, reconnect } = useSSEStream(sseUrl)

  const agentStatuses = useMemo(() => {
    const base = buildAgentStatuses(events)
    const runningStep = (status === 'streaming') ? determineRunningStep(events) : null
    if (runningStep && !base[runningStep]) {
      base[runningStep] = { status: 'running', message: '' }
    } else if (runningStep && base[runningStep]?.status === 'waiting') {
      base[runningStep] = { ...base[runningStep], status: 'running' }
    }
    return base
  }, [events, status])

  const stats    = useMemo(() => extractStats(events, report), [events, report])
  const isActive = status === 'connecting' || status === 'streaming'
  const isDone   = status === 'complete'
  const isError  = status === 'error'

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="min-h-screen bg-gradient-to-br from-slate-50 via-indigo-50/30 to-violet-50/20"
    >
      {/* Top nav */}
      <div className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-gray-100 px-4 md:px-8 py-3">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-2 text-sm text-gray-500 hover:text-indigo-600 transition-colors font-medium"
          >
            <ArrowLeft className="w-4 h-4" />
            New Analysis
          </button>

          <div className="flex items-center gap-2.5">
            <span className="text-xs font-mono text-gray-400 bg-gray-50 border border-gray-200 px-2.5 py-1 rounded">
              {jobId}
            </span>
            <span className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1 rounded-full
              ${isActive  ? 'status-running'
                : isDone  ? 'status-complete'
                : isError ? 'status-error'
                : 'status-waiting'}
            `}>
              {isActive && <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 pulse-dot" />}
              {isActive  ? 'Analyzing…'
               : isDone  ? 'Complete'
               : isError ? 'Error'
               : 'Starting…'}
            </span>
          </div>
        </div>
      </div>

      {/* Error banner */}
      {isError && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="max-w-6xl mx-auto mt-4 mx-4 px-4"
        >
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-red-700">Pipeline Error</p>
              <p className="text-xs text-red-600 mt-0.5">{error || 'An unexpected error occurred.'}</p>
            </div>
            <button
              onClick={reconnect}
              className="flex items-center gap-1.5 text-xs text-red-600 hover:text-red-800 font-medium px-3 py-1.5 bg-white border border-red-200 rounded-lg"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Retry
            </button>
          </div>
        </motion.div>
      )}

      {/* Main layout */}
      <div className="max-w-6xl mx-auto px-4 md:px-8 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* LEFT — Agent timeline */}
          <div className="space-y-4">
            <AgentTimeline agentStatuses={agentStatuses} isActive={isActive} />
          </div>

          {/* RIGHT — Stats + live log */}
          <div className="space-y-4">
            <StatCards stats={stats} />
            <LiveLog events={events} />
          </div>
        </div>

        {/* Results section — revealed on complete */}
        {isDone && report && (
          <motion.div
            initial={{ opacity: 0, scale: 0.97, y: 32 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ type: 'spring', stiffness: 200, damping: 22, delay: 0.2 }}
            className="mt-8"
          >
            <ResultsPage report={report} />
          </motion.div>
        )}
      </div>
    </motion.div>
  )
}
