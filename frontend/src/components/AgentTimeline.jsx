import { AnimatePresence, motion } from 'framer-motion'
import {
  Bug,
  CheckCircle,
  ChevronRight,
  Code2,
  Database,
  FileSearch,
  FileText,
  GitBranch,
  Loader2,
  Package,
  Search,
  Shield,
  SkipForward,
  Sparkles,
  Wrench,
  XCircle,
} from 'lucide-react'

const AGENTS = [
  {
    key: 'fetch', label: 'Fetcher', icon: Package,
    desc: 'Clones & reads the repository',
    running: 'Connecting to GitHub and downloading all source files from the repository…',
  },
  {
    key: 'parse', label: 'Parser', icon: Code2,
    desc: 'Extracts functions & structure',
    running: 'Reading each file with Tree-sitter to extract function names, line numbers, imports, and class definitions…',
  },
  {
    key: 'embed', label: 'Embedder', icon: GitBranch,
    desc: 'Creates semantic embeddings',
    running: 'Converting every code chunk into a numeric vector so the AI can understand meaning, not just keywords…',
  },
  {
    key: 'store', label: 'Vector Store', icon: Database,
    desc: 'Upserts chunks to Pinecone',
    running: 'Uploading all code vectors to Pinecone so agents can search by semantic similarity later…',
  },
  {
    key: 'orchestrate', label: 'Orchestrator', icon: Sparkles,
    desc: 'Identifies project type',
    running: 'Scanning the README and file structure to understand what this project does and how it\'s built…',
  },
  {
    key: 'plan', label: 'Planner', icon: ChevronRight,
    desc: 'Selects agents to activate',
    running: 'Deciding which specialist agents are relevant for this codebase — skipping ones that don\'t apply…',
  },
  {
    key: 'bug_detect', label: 'Bug Detector', icon: Bug,
    desc: 'Finds logic & runtime errors',
    running: 'Querying the vector store for risky code patterns, then asking the AI to identify real bugs with full context…',
  },
  {
    key: 'fix', label: 'Auto-Fixer', icon: Wrench,
    desc: 'Generates & verifies fixes',
    running: 'Writing corrected code for each bug, then running it in an E2B sandbox to confirm the fix actually works…',
  },
  {
    key: 'security', label: 'Security Auditor', icon: Shield,
    desc: 'Scans for vulnerabilities',
    running: 'Checking for SQL injection, exposed secrets, missing auth, weak crypto, and other OWASP Top 10 risks…',
  },
  {
    key: 'doc_check', label: 'Doc Checker', icon: FileText,
    desc: 'Reviews documentation coverage',
    running: 'Identifying functions missing docstrings or JSDoc, and evaluating README quality against a standard checklist…',
  },
  {
    key: 'quality', label: 'Code Quality', icon: Search,
    desc: 'Analyzes patterns & complexity',
    running: 'Measuring function lengths, nesting depth, naming quality, and duplicate code patterns across all files…',
  },
  {
    key: 'synthesize', label: 'Synthesizer', icon: FileSearch,
    desc: 'Assembles final report',
    running: 'Combining all agent findings into a structured report with an overall health score and executive summary…',
  },
]

function statusBadge(status) {
  switch (status) {
    case 'complete': return { cls: 'status-complete', label: 'Done' }
    case 'running':  return { cls: 'status-running',  label: 'Running' }
    case 'skipped':  return { cls: 'status-skipped',  label: 'Skipped' }
    case 'error':    return { cls: 'status-error',    label: 'Error' }
    default:         return { cls: 'status-waiting',  label: 'Waiting' }
  }
}

function StatusIcon({ status }) {
  const cls = 'w-5 h-5 flex-shrink-0'
  switch (status) {
    case 'complete': return <CheckCircle  className={`${cls} text-emerald-500`} />
    case 'running':  return <Loader2      className={`${cls} text-indigo-500 animate-spin`} />
    case 'skipped':  return <SkipForward  className={`${cls} text-amber-500`} />
    case 'error':    return <XCircle      className={`${cls} text-red-500`} />
    default:         return <div className={`${cls} rounded-full border-2 border-gray-200`} />
  }
}

export default function AgentTimeline({ agentStatuses, isActive }) {
  // agentStatuses: { fetch: { status, message }, ... }
  const statuses = agentStatuses || {}

  return (
    <div className="glass-card p-5">
      {/* Header */}
      <div className="flex items-center gap-2.5 mb-5">
        <h2 className="font-semibold text-gray-800 text-base">Agent Pipeline</h2>
        {isActive && (
          <span className="flex items-center gap-1.5 text-xs text-indigo-600 font-medium">
            <span className="w-2 h-2 rounded-full bg-emerald-400 pulse-dot" />
            Live
          </span>
        )}
      </div>

      {/* Timeline */}
      <div className="space-y-1.5">
        {AGENTS.map((agent, idx) => {
          const info   = statuses[agent.key] || {}
          const status = info.status || 'waiting'
          const badge  = statusBadge(status)
          const Icon   = agent.icon
          const isRunning = status === 'running'

          return (
            <motion.div
              key={agent.key}
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.04, duration: 0.3 }}
              className={`
                relative flex items-start gap-3 px-3 py-3 rounded-xl transition-all duration-300
                ${isRunning
                  ? 'bg-indigo-50/80 agent-running-border'
                  : status === 'complete'
                  ? 'bg-emerald-50/40 hover:bg-emerald-50/60'
                  : status === 'skipped'
                  ? 'bg-amber-50/30 hover:bg-amber-50/50'
                  : 'hover:bg-gray-50/80'
                }
              `}
            >
              {/* Left connector line (except last) */}
              {idx < AGENTS.length - 1 && (
                <div className={`
                  absolute left-[26px] top-[46px] w-px h-4 z-0
                  ${status === 'complete' ? 'bg-emerald-300' : 'bg-gray-200'}
                `} />
              )}

              {/* Icon circle */}
              <div className={`
                relative z-10 flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center
                ${status === 'complete' ? 'bg-emerald-100'
                  : isRunning ? 'bg-indigo-100'
                  : status === 'skipped' ? 'bg-amber-100'
                  : status === 'error' ? 'bg-red-100'
                  : 'bg-gray-100'}
              `}>
                <Icon className={`w-4 h-4
                  ${status === 'complete' ? 'text-emerald-600'
                    : isRunning ? 'text-indigo-600'
                    : status === 'skipped' ? 'text-amber-600'
                    : status === 'error' ? 'text-red-600'
                    : 'text-gray-400'}
                `} />
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span className={`text-sm font-medium
                    ${status === 'waiting' ? 'text-gray-400' : 'text-gray-800'}
                  `}>
                    {agent.label}
                  </span>
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    <StatusIcon status={status} />
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${badge.cls}`}>
                      {badge.label}
                    </span>
                  </div>
                </div>

                <AnimatePresence mode="wait">
                  {isRunning && !info.message ? (
                    <motion.p
                      key="running-desc"
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      className="text-xs text-indigo-500 mt-1 leading-relaxed"
                    >
                      {agent.running}
                    </motion.p>
                  ) : info.message && status !== 'waiting' ? (
                    <motion.p
                      key={info.message}
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      className="text-xs text-gray-500 mt-0.5 truncate"
                    >
                      {info.message}
                    </motion.p>
                  ) : null}
                </AnimatePresence>
              </div>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}
