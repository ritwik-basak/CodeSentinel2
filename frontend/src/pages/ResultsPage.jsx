import { motion } from 'framer-motion'
import {
  Braces,
  Calendar,
  CheckCircle2,
  ChevronRight,
  FileCode2,
  GitBranch,
  Languages,
  Sparkles,
  Target,
  Wrench,
  Zap,
} from 'lucide-react'
import CircularScore from '../components/CircularScore'
import ResultsTabs from '../components/ResultsTabs'

// ── Small helpers ────────────────────────────────────────────────────────────

function MetaPill({ icon: Icon, label, value }) {
  if (!value) return null
  return (
    <div className="flex items-center gap-1.5 bg-white/70 border border-gray-200/80 rounded-full px-3 py-1.5">
      <Icon className="w-3.5 h-3.5 text-gray-400" />
      <span className="text-gray-500 text-xs">{label}:</span>
      <span className="font-medium text-xs text-gray-700">{value}</span>
    </div>
  )
}

function HealthBadge({ health }) {
  const v = String(health || '').toLowerCase()
  if (v.includes('excellent') || v.includes('healthy') || v.includes('good'))
    return <span className="status-complete text-sm font-semibold px-3 py-1 rounded-full capitalize">{health}</span>
  if (v.includes('fair') || v.includes('moderate'))
    return <span className="severity-warning text-sm font-semibold px-3 py-1 rounded-full capitalize">{health}</span>
  return <span className="severity-critical text-sm font-semibold px-3 py-1 rounded-full capitalize">{health || 'Unknown'}</span>
}

// Language bar — shows breakdown as colored pills
const LANG_COLORS = {
  python:     { bg: 'bg-blue-100',   text: 'text-blue-700',   dot: 'bg-blue-400' },
  javascript: { bg: 'bg-yellow-100', text: 'text-yellow-700', dot: 'bg-yellow-400' },
  typescript: { bg: 'bg-sky-100',    text: 'text-sky-700',    dot: 'bg-sky-400' },
  html:       { bg: 'bg-orange-100', text: 'text-orange-700', dot: 'bg-orange-400' },
  css:        { bg: 'bg-pink-100',   text: 'text-pink-700',   dot: 'bg-pink-400' },
  java:       { bg: 'bg-red-100',    text: 'text-red-700',    dot: 'bg-red-400' },
  go:         { bg: 'bg-cyan-100',   text: 'text-cyan-700',   dot: 'bg-cyan-400' },
}
function defaultLang() { return { bg: 'bg-gray-100', text: 'text-gray-700', dot: 'bg-gray-400' } }

function LanguageBreakdown({ languages }) {
  if (!languages || Object.keys(languages).length === 0) return null
  const total  = Object.values(languages).reduce((a, b) => a + b, 0)
  const sorted = Object.entries(languages).sort((a, b) => b[1] - a[1])

  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Languages className="w-4 h-4 text-gray-400" />
        <h3 className="text-sm font-semibold text-gray-700">Language Breakdown</h3>
        <span className="text-xs text-gray-400">({total} files)</span>
      </div>

      {/* Progress bar */}
      <div className="flex h-2 rounded-full overflow-hidden mb-3 gap-px">
        {sorted.map(([lang, count]) => {
          const c = LANG_COLORS[lang] || defaultLang()
          return (
            <div
              key={lang}
              title={`${lang}: ${count} files`}
              className={`${c.dot} transition-all`}
              style={{ width: `${(count / total) * 100}%` }}
            />
          )
        })}
      </div>

      {/* Pills */}
      <div className="flex flex-wrap gap-2">
        {sorted.map(([lang, count]) => {
          const c    = LANG_COLORS[lang] || defaultLang()
          const pct  = Math.round((count / total) * 100)
          return (
            <span key={lang} className={`flex items-center gap-1.5 text-xs font-medium ${c.bg} ${c.text} px-2.5 py-1 rounded-full`}>
              <span className={`w-2 h-2 rounded-full ${c.dot}`} />
              {lang.charAt(0).toUpperCase() + lang.slice(1)}
              <span className="opacity-60">{count} ({pct}%)</span>
            </span>
          )
        })}
      </div>
    </div>
  )
}

// Fix summary card
function FixSummary({ fixes, bugs }) {
  if (!fixes || fixes.length === 0) return null
  const fixed       = fixes.filter(f => f.status === 'fixed').length
  const couldNotFix = fixes.filter(f => f.status === 'could_not_fix').length
  const pct         = fixes.length > 0 ? Math.round((fixed / fixes.length) * 100) : 0

  return (
    <div className="glass-card p-4 bg-gradient-to-r from-emerald-50/50 to-indigo-50/50">
      <div className="flex items-center gap-2 mb-3">
        <Wrench className="w-4 h-4 text-indigo-500" />
        <h3 className="text-sm font-semibold text-gray-700">Auto-Fix Results</h3>
      </div>
      <div className="flex items-center gap-6 flex-wrap">
        <div className="text-center">
          <div className="text-3xl font-bold text-emerald-600 tabular-nums">{fixed}</div>
          <div className="text-xs text-gray-500 mt-0.5">Fixed</div>
        </div>
        <div className="text-center">
          <div className="text-3xl font-bold text-red-400 tabular-nums">{couldNotFix}</div>
          <div className="text-xs text-gray-500 mt-0.5">Could not fix</div>
        </div>
        <div className="flex-1 min-w-[120px]">
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>Success rate</span>
            <span className="font-semibold text-gray-700">{pct}%</span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-gradient-to-r from-emerald-400 to-emerald-500 rounded-full"
              initial={{ width: 0 }}
              animate={{ width: `${pct}%` }}
              transition={{ duration: 1, delay: 0.5, ease: 'easeOut' }}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

// Agents activated
function AgentsActivated({ agents }) {
  if (!agents || agents.length === 0) return null
  const labels = {
    bug_detector:    { label: 'Bug Detector',    icon: '🐛' },
    security_auditor:{ label: 'Security Auditor', icon: '🔒' },
    doc_checker:     { label: 'Doc Checker',      icon: '📄' },
    code_quality:    { label: 'Code Quality',     icon: '⭐' },
    fixer:           { label: 'Auto-Fixer',       icon: '🔧' },
  }
  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles className="w-4 h-4 text-indigo-400" />
        <h3 className="text-sm font-semibold text-gray-700">Agents Activated</h3>
        <span className="text-xs text-gray-400">({agents.length} of 4)</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {agents.map((a) => {
          const info = labels[a] || { label: a, icon: '🤖' }
          return (
            <span key={a} className="flex items-center gap-1.5 text-xs font-medium text-indigo-700 bg-indigo-50 border border-indigo-200 px-2.5 py-1 rounded-full">
              <span>{info.icon}</span>
              {info.label}
            </span>
          )
        })}
      </div>
    </div>
  )
}

// Top priorities + strengths
function InsightsSection({ summary }) {
  const priorities = summary?.top_priorities || []
  const strengths  = summary?.strengths      || []
  const verdict    = summary?.verdict

  if (priorities.length === 0 && strengths.length === 0 && !verdict) return null

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {priorities.length > 0 && (
        <div className="glass-card p-4">
          <div className="flex items-center gap-2 mb-3">
            <Target className="w-4 h-4 text-red-400" />
            <h3 className="text-sm font-semibold text-gray-700">Top Priorities</h3>
          </div>
          <ol className="space-y-2">
            {priorities.map((p, i) => (
              <li key={i} className="flex items-start gap-2.5">
                <span className="flex-shrink-0 w-5 h-5 rounded-full bg-red-100 text-red-600 text-[10px] font-bold flex items-center justify-center mt-0.5">
                  {i + 1}
                </span>
                <p className="text-sm text-gray-700 leading-relaxed">{p}</p>
              </li>
            ))}
          </ol>
        </div>
      )}

      <div className="space-y-4">
        {strengths.length > 0 && (
          <div className="glass-card p-4">
            <div className="flex items-center gap-2 mb-3">
              <Zap className="w-4 h-4 text-amber-400" />
              <h3 className="text-sm font-semibold text-gray-700">Strengths</h3>
            </div>
            <ul className="space-y-2">
              {strengths.map((s, i) => (
                <li key={i} className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-gray-700 leading-relaxed">{s}</p>
                </li>
              ))}
            </ul>
          </div>
        )}

        {verdict && (
          <div className="glass-card p-4 bg-indigo-50/40 border border-indigo-100">
            <div className="flex items-center gap-2 mb-2">
              <ChevronRight className="w-4 h-4 text-indigo-400" />
              <h3 className="text-sm font-semibold text-gray-700">Verdict</h3>
            </div>
            <p className="text-sm text-gray-700 leading-relaxed italic">"{verdict}"</p>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function ResultsPage({ report }) {
  if (!report) return null

  const summary  = report.summary  || {}
  const metadata = report.metadata || {}

  const repoUrl  = report.repo_url || metadata.repo_url
  const repoName = repoUrl ? repoUrl.replace(/\/$/, '').split('/').slice(-2).join('/') : 'Repository'

  const timestamp     = metadata.generated_at || metadata.timestamp || report.generated_at
  const formattedDate = timestamp
    ? new Date(timestamp).toLocaleString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
      })
    : null

  const health       = summary.overall_health || summary.verdict || 'Unknown'
  const score        = summary.health_score   != null ? summary.health_score : 0
  const execSummary  = summary.executive_summary || summary.summary || summary.overview

  const totalFiles       = metadata.total_files        || summary.total_files
  const totalFunctions   = metadata.total_functions    || summary.total_functions
  const languages        = metadata.languages          || {}
  const projectType      = metadata.project_type       || ''
  const projectDesc      = metadata.project_description || ''
  const agentsActivated  = report.agents_activated     || []
  const fixes            = report.fixes                || []

  return (
    <div className="space-y-5">
      {/* ── Header card ──────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-card p-6 md:p-8"
      >
        <div className="flex flex-col md:flex-row gap-6">
          {/* Score ring */}
          <div className="flex-shrink-0 flex justify-center md:justify-start">
            <CircularScore score={score} label="Health Score" />
          </div>

          {/* Meta */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-2">
              <GitBranch className="w-4 h-4 text-gray-400" />
              <h2 className="text-lg font-bold text-gray-900">{repoName}</h2>
              <HealthBadge health={health} />
            </div>

            <div className="flex flex-wrap gap-2 mb-4">
              <MetaPill icon={FileCode2} label="Files"     value={totalFiles}     />
              <MetaPill icon={Braces}    label="Functions" value={totalFunctions} />
              {formattedDate && <MetaPill icon={Calendar} label="Analyzed" value={formattedDate} />}
            </div>

            {/* Project description — what this repo is about */}
            {(projectType || projectDesc) && (
              <div className="mb-3 p-3.5 bg-white/70 border border-gray-200 rounded-xl">
                <div className="flex items-center gap-2 mb-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                  {projectType && (
                    <span className="text-[11px] font-semibold uppercase tracking-wide text-indigo-500">
                      {projectType}
                    </span>
                  )}
                </div>
                {projectDesc && (
                  <p className="text-sm text-gray-700 leading-relaxed">{projectDesc}</p>
                )}
              </div>
            )}

            {execSummary && (
              <div className="bg-indigo-50/60 border border-indigo-100 rounded-xl p-4">
                <p className="text-xs font-semibold text-indigo-500 uppercase tracking-wide mb-1.5">Analysis Summary</p>
                <p className="text-sm text-gray-700 leading-relaxed">{execSummary}</p>
              </div>
            )}
          </div>
        </div>
      </motion.div>

      {/* ── Insight cards row ─────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.08 }}
        className="grid grid-cols-1 md:grid-cols-3 gap-4"
      >
        <LanguageBreakdown languages={languages} />
        <AgentsActivated agents={agentsActivated} />
        <FixSummary fixes={fixes} bugs={report.bugs} />
      </motion.div>

      {/* ── Priorities + Strengths + Verdict ──────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.14 }}
      >
        <InsightsSection summary={summary} />
      </motion.div>

      {/* ── Tabs ──────────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <ResultsTabs report={report} />
      </motion.div>
    </div>
  )
}
