import { AnimatePresence, motion } from 'framer-motion'
import {
  AlertCircle,
  AlertTriangle,
  BookOpen,
  Bug,
  CheckCircle2,
  Code2,
  FileCode,
  FileText,
  FolderOpen,
  Hash,
  Lightbulb,
  Shield,
  Star,
  TrendingUp,
} from 'lucide-react'
import { useState } from 'react'
import BugCard from './BugCard'

// ── Shared code location block (reused across Security, Quality, Docs tabs) ──
function CodeLocation({ filename, functionName, line }) {
  if (!filename && !functionName && !line) return null
  const parts  = (filename || '').replace(/\\/g, '/').split('/')
  const file   = parts.pop() || filename
  const folder = parts.length > 0 ? parts.join('/') + '/' : ''
  return (
    <div className="mt-3 rounded-lg border border-indigo-100 bg-indigo-50/40 overflow-hidden">
      {folder && (
        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-50 border-b border-indigo-100">
          <FolderOpen className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
          <span className="text-xs font-mono text-indigo-400 truncate">{folder}</span>
        </div>
      )}
      <div className="flex items-center gap-3 px-3 py-2 flex-wrap">
        <div className="flex items-center gap-1.5">
          <FileCode className="w-3.5 h-3.5 text-indigo-600 flex-shrink-0" />
          <span className="text-sm font-mono font-semibold text-indigo-700">{file}</span>
        </div>
        {functionName && (
          <div className="flex items-center gap-1.5">
            <span className="text-gray-300">·</span>
            <Code2 className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
            <span className="text-sm font-mono text-indigo-600">
              <span className="text-gray-400 text-xs">fn</span> {functionName}
            </span>
          </div>
        )}
        {line && (
          <div className="flex items-center gap-1">
            <span className="text-gray-300">·</span>
            <Hash className="w-3 h-3 text-gray-400" />
            <span className="text-xs font-mono font-semibold text-gray-600 bg-white border border-gray-200 px-1.5 py-0.5 rounded">
              Line {line}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

const TABS = [
  { id: 'bugs',     label: 'Bugs & Fixes',  icon: Bug      },
  { id: 'security', label: 'Security',       icon: Shield   },
  { id: 'quality',  label: 'Code Quality',   icon: Star     },
  { id: 'docs',     label: 'Documentation',  icon: BookOpen },
]

// ── Generic fix suggestions by keyword ──────────────────────────────────────
function genericFixTip(title) {
  const t = String(title || '').toLowerCase()
  if (t.includes('sql') || t.includes('inject'))
    return 'SQL injection happens when user-supplied text is pasted directly into a database query. An attacker can type carefully crafted input like \' OR 1=1-- that changes the meaning of the query and tricks the database into returning data it shouldn\'t — or even deleting everything. The fix is to use parameterized queries (also called prepared statements), where the user input is sent to the database separately from the query structure, so it can never alter the query logic. Most ORMs (like SQLAlchemy, Prisma, Django ORM) do this automatically — prefer them over writing raw SQL with string concatenation.'
  if (t.includes('xss') || t.includes('cross-site'))
    return 'Cross-Site Scripting (XSS) happens when user-supplied text is inserted into a webpage without being sanitized first, and the browser interprets it as executable JavaScript. An attacker can inject a script tag that steals session cookies, redirects users to a phishing site, or logs every keystroke. The fix is to always escape user content before rendering it — in React, avoid dangerouslySetInnerHTML with untrusted data, and in plain JavaScript use textContent instead of innerHTML. Adding a Content-Security-Policy header provides an extra layer of defence.'
  if (t.includes('auth') || t.includes('unauthorized'))
    return 'Authentication checks are missing or incomplete on this endpoint, meaning a user who is not logged in (or not authorized) can still access it. This is one of the most common causes of data breaches — an attacker simply skips the login page and calls the API directly. The fix is to add an authentication middleware that verifies the session token or JWT on every protected route before any business logic runs. Never rely on the frontend to "hide" routes from unauthorized users — always enforce access control on the server.'
  if (t.includes('password') || t.includes('credential'))
    return 'Passwords and secrets should never be stored as plain text. If your database is ever breached, plain-text passwords give an attacker immediate access to every account, including users who reuse the same password elsewhere. The fix is to hash passwords using a slow, purpose-built algorithm like bcrypt, scrypt, or Argon2 before storing them. These algorithms are deliberately slow to make brute-force guessing impractical. For API keys and secrets, store them in environment variables or a secrets manager — never hardcode them in source files or commit them to Git.'
  if (t.includes('crypt') || t.includes('md5') || t.includes('sha1'))
    return 'MD5 and SHA-1 are old cryptographic algorithms that are now broken — researchers can generate two different inputs that produce the same hash (called a collision) in seconds on modern hardware. This makes them useless for verifying data integrity or hashing passwords. Replace them with SHA-256 or SHA-3 for general hashing, and AES-256-GCM for symmetric encryption. If you are using these for passwords specifically, switch to bcrypt or Argon2 instead, which are specifically designed to resist brute-force attacks.'
  if (t.includes('path') || t.includes('traversal'))
    return 'Path traversal happens when user input is used to construct a file path without checking whether the resulting path stays inside the expected directory. An attacker can supply a value like ../../.env to escape the intended folder and read sensitive files anywhere on the server — including environment files with API keys, SSH private keys, or system configuration. The fix is to resolve the full absolute path of the target file and verify it starts with the expected base directory before opening it. Reject any input containing ".." sequences before it reaches file system code.'
  if (t.includes('env') || t.includes('secret') || t.includes('key') || t.includes('token') || t.includes('api key'))
    return 'Secrets like API keys, database passwords, and tokens should never appear in source code. If they are committed to a Git repository — even once, even in a branch that gets deleted — they can be recovered from the history and are considered compromised. The fix is to move all secrets into a .env file (never committed), load them at runtime using a library like dotenv, and add .env to your .gitignore. For production, use your hosting platform\'s secrets manager (e.g. AWS Secrets Manager, Railway environment variables, Vercel environment settings). Rotate any secret that has already been exposed.'
  if (t.includes('log') || t.includes('sensitiv'))
    return 'Log statements that include sensitive data — user emails, passwords, session tokens, API keys, or personal details — create a secondary breach risk. Logs are often stored in multiple places (files, third-party services, cloud buckets) and retained for months or years. If any of those systems is accessed by an unauthorized person, every piece of sensitive data in the logs is exposed. The fix is to audit every log call and remove or redact sensitive fields. Use structured logging with an explicit allowlist of safe fields rather than logging entire request objects.'
  if (t.includes('cors') || t.includes('origin'))
    return 'CORS (Cross-Origin Resource Sharing) controls which websites are allowed to make requests to your API from a browser. Setting Access-Control-Allow-Origin: * means any website on the internet can make requests to your API on behalf of a logged-in user — including malicious ones. This can enable an attacker\'s site to silently read or modify a user\'s data while they are browsing. The fix is to replace the wildcard with an explicit allowlist of trusted domains (e.g. your frontend\'s production URL). Only add Access-Control-Allow-Credentials: true if your API specifically needs to receive cookies.'
  if (t.includes('input') || t.includes('validat'))
    return 'This code accepts input from an external source (user, API, form) and uses it without first checking whether it is safe and in the expected format. Unvalidated input is the root cause of most injection attacks, crashes from unexpected data types, and logic errors from out-of-range values. The fix is to validate every piece of external input at the boundary where it enters your system — check the type, length, format, and allowed value range. Use a schema validation library (like Pydantic for Python, Zod for TypeScript, or Joi for JavaScript) to make this structured and maintainable.'
  if (t.includes('error') || t.includes('handl'))
    return 'This code performs an operation that can fail — like a network call, file read, or database query — but does not handle the failure case. If something goes wrong, the error will propagate uncontrolled and either crash the application or produce an undefined result. Worse, some frameworks will automatically send the raw error message (including stack traces and file paths) back to the client, which gives an attacker a detailed map of your server. The fix is to wrap risky operations in try/catch blocks, log the full error server-side for debugging, and return only a safe generic message to the client.'
  return 'This vulnerability falls into a known security risk category. Review the OWASP Top 10 (https://owasp.org/www-project-top-ten/) for the specific mitigation guidance that applies here. As a general rule: never trust external input, always enforce authorization on the server, keep secrets out of code, and add security headers to every HTTP response. Consider adding an automated security scanner (Semgrep, Bandit, or ESLint-plugin-security) to your CI pipeline so issues like this are caught before they reach production.'
}

// ── Security tab ─────────────────────────────────────────────────────────────
function VulnCard({ vuln, index }) {
  const [showCode, setShowCode] = useState(false)
  const sev        = String(vuln?.severity || '').toLowerCase()
  const isCritical = sev === 'critical' || sev === 'high'
  // Prefer actual secure_fix from data, fall back to generic tip
  const fixText    = vuln?.secure_fix || vuln?.suggestion || vuln?.recommendation || genericFixTip(vuln?.title || vuln?.type)
  const vulnCode   = vuln?.vulnerable_code

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06 }}
      className="glass-card p-4"
    >
      <div className="flex items-start gap-3">
        <div className={`flex-shrink-0 p-2 rounded-lg ${isCritical ? 'bg-red-50' : 'bg-amber-50'}`}>
          <Shield className={`w-4 h-4 ${isCritical ? 'text-red-500' : 'text-amber-500'}`} />
        </div>
        <div className="flex-1 min-w-0">
          {/* Severity + CWE badges */}
          <div className="flex items-center gap-2 flex-wrap mb-1.5">
            <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${isCritical ? 'severity-critical' : 'severity-warning'}`}>
              {vuln?.severity || 'warning'}
            </span>
            {(vuln?.cwe || vuln?.owasp) && (
              <span className="text-[11px] font-mono text-gray-400 bg-gray-50 border border-gray-200 px-2 py-0.5 rounded">
                {vuln?.cwe || vuln?.owasp}
              </span>
            )}
          </div>

          <h3 className="text-sm font-semibold text-gray-800">{vuln?.title || vuln?.type || 'Vulnerability'}</h3>

          {vuln?.description && (
            <p className="text-sm text-gray-600 mt-1.5 leading-relaxed">{vuln.description}</p>
          )}

          {/* Code location — full folder / file / function / line */}
          <CodeLocation
            filename={vuln?.filename || vuln?.file}
            functionName={vuln?.function_name || vuln?.func}
            line={vuln?.line}
          />

          {/* Vulnerable code snippet */}
          {vulnCode && (
            <div className="mt-3">
              <button
                onClick={() => setShowCode(v => !v)}
                className="text-[11px] font-medium text-red-500 hover:text-red-700 transition-colors"
              >
                {showCode ? '▲ Hide vulnerable code' : '▼ Show vulnerable code'}
              </button>
              <AnimatePresence>
                {showCode && (
                  <motion.pre
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="mt-2 text-xs font-mono bg-red-50 border border-red-200 text-red-800 p-3 rounded-lg overflow-x-auto leading-relaxed"
                  >
                    {vulnCode}
                  </motion.pre>
                )}
              </AnimatePresence>
            </div>
          )}

          {/* Suggested fix */}
          <div className="mt-3 p-3.5 bg-amber-50 border border-amber-200 rounded-lg">
            <div className="flex items-start gap-2">
              <Lightbulb className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-1.5">How to Fix This</p>
                <p className="text-sm text-amber-900 leading-relaxed">{fixText}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

// ── Code Quality tab ─────────────────────────────────────────────────────────
const ISSUE_TYPE_META = {
  too_long:       { label: 'Too Long',        icon: '📏', color: 'bg-red-50 border-red-200 text-red-700' },
  too_complex:    { label: 'Complex',         icon: '🔀', color: 'bg-purple-50 border-purple-200 text-purple-700' },
  deep_nesting:   { label: 'Deep Nesting',    icon: '🪆', color: 'bg-orange-50 border-orange-200 text-orange-700' },
  poor_naming:    { label: 'Poor Naming',     icon: '🏷️', color: 'bg-amber-50 border-amber-200 text-amber-700' },
  missing_types:  { label: 'Missing Types',   icon: '❓', color: 'bg-gray-50 border-gray-200 text-gray-700' },
  duplicate_code: { label: 'Duplicate Code',  icon: '♻️', color: 'bg-blue-50 border-blue-200 text-blue-700' },
}

function IssueTypeBadge({ type }) {
  const m = ISSUE_TYPE_META[type]
  if (!m) return null
  return (
    <span className={`flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded border ${m.color}`}>
      <span>{m.icon}</span>
      {m.label}
    </span>
  )
}

function SeverityDot({ severity }) {
  const s = String(severity || '').toLowerCase()
  if (s === 'critical') return <span className="w-2 h-2 rounded-full bg-red-500 flex-shrink-0 mt-1.5" title="Critical" />
  if (s === 'warning')  return <span className="w-2 h-2 rounded-full bg-amber-400 flex-shrink-0 mt-1.5" title="Warning" />
  return                       <span className="w-2 h-2 rounded-full bg-blue-300 flex-shrink-0 mt-1.5" title="Suggestion" />
}

function LongestFunctions({ fns }) {
  if (!fns || fns.length === 0) return null
  const max = Math.max(...fns.map(f => f.approx_lines || 0))

  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="w-4 h-4 text-indigo-400" />
        <h4 className="text-sm font-semibold text-gray-700">Longest Functions</h4>
        <span className="text-xs text-gray-400">Top {fns.length} by line count</span>
      </div>
      <div className="space-y-4">
        {fns.map((f, i) => {
          const lines  = f.approx_lines || 0
          const barPct = max > 0 ? (lines / max) * 100 : 0
          const isLong = lines > 100
          const parts  = (f.filename || '').replace(/\\/g, '/').split('/')
          const fname  = parts.slice(-1)[0] || f.filename || ''
          return (
            <div key={i}>
              <div className="flex items-start justify-between mb-1.5 gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <FileCode className="w-3.5 h-3.5 text-indigo-500 flex-shrink-0" />
                    <span className="text-sm font-mono font-semibold text-indigo-700">{fname}</span>
                    {f.function_name && (
                      <>
                        <span className="text-gray-300">·</span>
                        <Code2 className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
                        <span className="text-sm font-mono text-indigo-600">
                          <span className="text-gray-400 text-xs">fn</span> {f.function_name}
                        </span>
                      </>
                    )}
                    {f.line && (
                      <>
                        <span className="text-gray-300">·</span>
                        <span className="text-xs font-mono font-semibold text-gray-600 bg-white border border-gray-200 px-1.5 py-0.5 rounded">
                          Line {f.line}
                        </span>
                      </>
                    )}
                  </div>
                  {parts.length > 1 && (
                    <span className="text-[11px] font-mono text-gray-400 mt-0.5 block">
                      {parts.slice(0, -1).join('/') + '/'}
                    </span>
                  )}
                </div>
                <span className={`text-sm font-bold tabular-nums flex-shrink-0 ${isLong ? 'text-red-500' : 'text-gray-500'}`}>
                  {lines} lines
                </span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <motion.div
                  className={`h-full rounded-full ${isLong ? 'bg-red-400' : 'bg-indigo-400'}`}
                  initial={{ width: 0 }}
                  animate={{ width: `${barPct}%` }}
                  transition={{ duration: 0.7, delay: i * 0.1, ease: 'easeOut' }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function QualityTab({ qualityResult }) {
  const r          = qualityResult || {}
  const score      = r.score ?? r.overall_quality_score ?? null
  const summary    = r.summary || ''
  const issues     = r.issues || r.findings || []
  const longestFns = r.longest_functions || []

  // Counts for context (NOT used to derive the score)
  const criticalCount = issues.filter(f => String(f.severity || '').toLowerCase() === 'critical').length
  const warningCount  = issues.filter(f => String(f.severity || '').toLowerCase() === 'warning').length
  const otherCount    = issues.length - criticalCount - warningCount

  // Group by issue_type for badge summary
  const byType = issues.reduce((acc, f) => {
    const t = f.issue_type || 'other'
    acc[t] = (acc[t] || 0) + 1
    return acc
  }, {})

  const scoreColor = score === null ? '#6366f1'
    : score >= 80 ? '#059669'
    : score >= 60 ? '#D97706'
    : '#DC2626'

  return (
    <div className="space-y-4">
      {/* Score card */}
      {score !== null && (
        <div className="glass-card p-6 bg-gradient-to-r from-violet-50 to-indigo-50">
          <div className="flex flex-col md:flex-row items-start gap-6">
            {/* Big number */}
            <div className="flex-shrink-0 text-center">
              <div className="tabular-nums font-bold" style={{ fontSize: '80px', lineHeight: 1, color: scoreColor }}>
                {score}
              </div>
              <p className="text-sm font-semibold text-gray-700 mt-1">Quality Score</p>
              <p className="text-xs text-gray-400">out of 100</p>
            </div>

            <div className="flex-1 min-w-0 space-y-4">
              {/* How the score works */}
              <div className="bg-white/60 border border-gray-200 rounded-lg p-3 space-y-2">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">How this score was calculated</p>
                <p className="text-sm text-gray-600 leading-relaxed">
                  This score is assigned by an AI model that reads a sample of the codebase and rates it holistically on naming conventions, complexity, function length, code duplication, and maintainability — similar to a code review from a senior engineer.
                </p>
                {summary && (
                  <p className="text-sm text-gray-700 leading-relaxed pt-1 border-t border-gray-100">
                    {summary}
                  </p>
                )}
                {/* Issue counts as context, not causation */}
                {issues.length > 0 && (
                  <div className="pt-2 border-t border-gray-100 space-y-1">
                    <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1.5">Issues found during analysis</p>
                    {criticalCount > 0 && (
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-red-600">Critical</span>
                        <span className="font-semibold tabular-nums text-red-600">{criticalCount}</span>
                      </div>
                    )}
                    {warningCount > 0 && (
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-amber-600">Warnings</span>
                        <span className="font-semibold tabular-nums text-amber-600">{warningCount}</span>
                      </div>
                    )}
                    {otherCount > 0 && (
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-500">Suggestions</span>
                        <span className="font-semibold tabular-nums text-gray-500">{otherCount}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Issue type badges */}
              {Object.keys(byType).length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Issue Types Found</p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(byType).map(([type, count]) => {
                      const m = ISSUE_TYPE_META[type]
                      return (
                        <span key={type} className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded border ${m?.color || 'bg-gray-50 border-gray-200 text-gray-700'}`}>
                          <span>{m?.icon || '⚠️'}</span>
                          {m?.label || type}
                          <span className="font-bold">×{count}</span>
                        </span>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Longest functions chart */}
      <LongestFunctions fns={longestFns} />

      {/* Issues list */}
      {issues.length > 0 ? (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 px-1">
            All Issues ({issues.length})
          </p>
          <div className="space-y-2.5">
            {issues.map((f, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.03 }}
                className="glass-card p-4"
              >
                <div className="flex items-start gap-3">
                  <SeverityDot severity={f.severity} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1.5">
                      {f.issue_type && <IssueTypeBadge type={f.issue_type} />}
                    </div>
                    {(f.title || f.issue) && (
                      <p className="text-sm font-semibold text-gray-800 leading-snug">
                        {f.title || f.issue}
                      </p>
                    )}
                    {f.description && (
                      <p className="text-sm text-gray-600 mt-1 leading-relaxed">{f.description}</p>
                    )}
                    {/* Code location */}
                    <CodeLocation
                      filename={f.filename || f.file}
                      functionName={f.function_name || f.func}
                      line={f.line}
                    />
                    {f.suggestion && (
                      <p className="text-sm text-indigo-700 mt-2 pl-3 border-l-2 border-indigo-200 italic leading-relaxed">
                        {f.suggestion}
                      </p>
                    )}
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      ) : (
        <EmptyState icon={CheckCircle2} message="No code quality issues found." color="emerald" />
      )}
    </div>
  )
}

// ── Documentation tab ────────────────────────────────────────────────────────

const README_CHECKLIST = [
  {
    key: 'description',
    label: 'Project description',
    tip: 'A good README starts by answering "what does this project do?" in plain English. It should explain the problem it solves, who it is for, and what makes it useful — in a short paragraph or two. Without this, a developer landing on your repo has no idea whether it is relevant to them.',
  },
  {
    key: 'setup',
    label: 'Setup instructions',
    tip: 'Step-by-step instructions for getting the project running locally — including prerequisites (e.g. Python 3.10+, Node 18+), how to install dependencies, how to configure environment variables, and how to start the server. Someone who has never seen your code should be able to follow these instructions and have it running within minutes.',
  },
  {
    key: 'usage',
    label: 'Usage examples',
    tip: 'Show at least one real example of how to use the project — a code snippet, a terminal command, or a screenshot. Usage examples help developers understand what the project actually looks like in action, not just in theory. They also serve as a quick sanity check that the setup worked correctly.',
  },
  {
    key: 'api',
    label: 'API documentation',
    tip: 'If your project exposes HTTP endpoints, a function library, or a CLI, document them. For HTTP APIs this means listing each route (method + path), what parameters it accepts, and what it returns. Without this, anyone integrating with your project has to read the source code to figure out how to call it — which is slow and error-prone.',
  },
  {
    key: 'env',
    label: 'Environment variables',
    tip: 'List every environment variable your project requires (API keys, database URLs, feature flags, etc.) with a short description of what each one does and where to get it. Include a .env.example file in your repo as a template. Missing env var documentation is one of the most common reasons a project fails to run on a new machine.',
  },
  {
    key: 'contributing',
    label: 'Contributing guidelines',
    tip: 'Explain how others (or your future self) can contribute to the project — how to fork and clone, which branch to target, how to run tests before submitting, and what the PR review process looks like. Even a short paragraph helps set expectations and reduces back-and-forth when collaborators submit changes.',
  },
]

// Infer checklist state from readme_quality string
function inferReadmeItems(quality) {
  const q = String(quality || '').toLowerCase()
  if (q === 'good' || q === 'excellent')   return { description: true, setup: true, usage: true, api: true, env: true, contributing: true }
  if (q === 'fair' || q === 'moderate')    return { description: true, setup: true, usage: true, api: false, env: false, contributing: false }
  if (q === 'poor' || q === 'missing' || q === 'none') return { description: false, setup: false, usage: false, api: false, env: false, contributing: false }
  // unknown quality — all null (show as "not assessed")
  return {}
}

function ReadmeChecklist({ readmeQuality, readmeAssessment }) {
  // Use actual per-field booleans from LLM if available, otherwise infer from quality string
  const items = (readmeAssessment && Object.keys(readmeAssessment).length > 0)
    ? {
        description:  readmeAssessment.has_description  ?? null,
        setup:        readmeAssessment.has_setup         ?? null,
        usage:        readmeAssessment.has_usage         ?? null,
        api:          readmeAssessment.has_api_docs      ?? null,
        env:          readmeAssessment.has_env_vars      ?? null,
        contributing: readmeAssessment.has_contributing  ?? null,
      }
    : inferReadmeItems(readmeQuality)
  const qLower = String(readmeQuality || '').toLowerCase()

  const badgeCls = qLower === 'good' || qLower === 'excellent'
    ? 'status-complete'
    : qLower === 'fair' || qLower === 'moderate'
    ? 'severity-warning'
    : qLower === 'poor' || qLower === 'missing'
    ? 'severity-critical'
    : 'status-waiting'

  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-gray-400" />
          <h4 className="text-sm font-semibold text-gray-700">README Checklist</h4>
        </div>
        {readmeQuality && (
          <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${badgeCls} capitalize`}>
            {readmeQuality}
          </span>
        )}
      </div>

      <div className="space-y-2">
        {README_CHECKLIST.map((item) => {
          const state = items[item.key]   // true = present, false = missing, null/undefined = unknown
          return (
            <div key={item.key} className={`flex items-start gap-3 p-2.5 rounded-lg border ${
              state === true  ? 'bg-emerald-50/60 border-emerald-100'
              : state === false ? 'bg-red-50/40 border-red-100'
              : 'bg-gray-50/60 border-gray-100'
            }`}>
              <div className="flex-shrink-0 mt-0.5">
                {state === true  && <CheckCircle2 className="w-4 h-4 text-emerald-500" />}
                {state === false && <AlertCircle  className="w-4 h-4 text-red-400" />}
                {state == null   && <AlertCircle  className="w-4 h-4 text-gray-300" />}
              </div>
              <div className="min-w-0">
                <p className={`text-sm font-medium ${
                  state === true ? 'text-emerald-800' : state === false ? 'text-red-700' : 'text-gray-600'
                }`}>
                  {item.label}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">{item.tip}</p>
              </div>
              <div className="ml-auto flex-shrink-0">
                <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                  state === true  ? 'bg-emerald-100 text-emerald-700'
                  : state === false ? 'bg-red-100 text-red-600'
                  : 'bg-gray-100 text-gray-500'
                }`}>
                  {state === true ? '✓ Present' : state === false ? '✗ Missing' : '? Unknown'}
                </span>
              </div>
            </div>
          )
        })}
      </div>

      <p className="text-[11px] text-gray-400 mt-3 text-center italic">
        Based on automated README analysis · Manual review recommended
      </p>
    </div>
  )
}

function DocsTab({ docResult }) {
  const r                = docResult || {}
  const score            = r.score ?? r.documentation_score ?? null
  const fnDocScore       = r.fn_doc_score   ?? null
  const readmeScore      = r.readme_score   ?? null
  const readmeChecked    = r.readme_checked ?? null
  const documentedCount  = r.documented_count  ?? null
  const totalFunctions   = r.total_functions   ?? null
  const undocumentedCount = r.undocumented_count ?? null
  const readmeQuality    = r.readme_quality
  const readmeAssessment = r.readme_assessment || {}
  const findings         = r.findings || []
  const summary          = r.summary  || r.overview

  const scoreColor = score === null ? '#9CA3AF'
    : score > 60 ? '#059669'
    : score >= 30 ? '#D97706'
    : '#DC2626'
  const scoreBg = score === null ? 'bg-gray-50'
    : score > 60 ? 'bg-gradient-to-r from-emerald-50 to-teal-50'
    : score >= 30 ? 'bg-gradient-to-r from-amber-50 to-yellow-50'
    : 'bg-gradient-to-r from-red-50 to-rose-50'

  const hasSplitScores = fnDocScore !== null && readmeScore !== null

  return (
    <div className="space-y-4">
      {/* Score card — matches Quality tab style */}
      {score !== null && (
        <div className={`glass-card p-6 ${scoreBg}`}>
          <div className="flex flex-col md:flex-row items-start gap-6">
            <div className="flex-shrink-0 text-center">
              <div className="tabular-nums font-bold" style={{ fontSize: '80px', lineHeight: 1, color: scoreColor }}>
                {score}
              </div>
              <p className="text-sm font-semibold text-gray-700 mt-1">Documentation Score</p>
              <p className="text-xs text-gray-400">out of 100</p>
            </div>

            <div className="flex-1 min-w-0 space-y-4">
              <div className="bg-white/60 border border-gray-200 rounded-lg p-3 space-y-2">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">How this score was calculated</p>
                <p className="text-sm text-gray-600 leading-relaxed">
                  This score combines two signals: <strong>70% from inline documentation</strong> (docstrings in Python, JSDoc in JavaScript/TypeScript) and <strong>30% from README completeness</strong> (how many of the 6 key README sections are present). This gives a fuller picture of how well a project is documented — a codebase can have perfect docstrings but no README, or a great README but undocumented code.
                </p>
                {summary && (
                  <p className="text-sm text-gray-700 leading-relaxed pt-1 border-t border-gray-100">
                    {summary}
                  </p>
                )}

                {/* Split score bars */}
                {hasSplitScores && (
                  <div className="pt-2 border-t border-gray-100 space-y-3">
                    <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">Score breakdown</p>

                    {/* Function doc coverage — 70% weight */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-600">
                          Inline docs <span className="text-xs text-gray-400">(docstrings / JSDoc) · 70%</span>
                        </span>
                        <span className="font-semibold tabular-nums" style={{ color: fnDocScore > 60 ? '#059669' : fnDocScore >= 30 ? '#D97706' : '#DC2626' }}>
                          {fnDocScore}/100
                        </span>
                      </div>
                      {totalFunctions != null && (
                        <p className="text-xs text-gray-400">{documentedCount} of {totalFunctions} functions documented</p>
                      )}
                      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <motion.div
                          className="h-full rounded-full"
                          style={{ background: fnDocScore > 60 ? '#059669' : fnDocScore >= 30 ? '#D97706' : '#DC2626' }}
                          initial={{ width: 0 }}
                          animate={{ width: `${fnDocScore}%` }}
                          transition={{ duration: 1, ease: 'easeOut' }}
                        />
                      </div>
                    </div>

                    {/* README completeness — 30% weight */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-600">
                          README completeness · <span className="text-xs text-gray-400">30%</span>
                        </span>
                        <span className="font-semibold tabular-nums" style={{ color: readmeScore > 60 ? '#059669' : readmeScore >= 30 ? '#D97706' : '#DC2626' }}>
                          {readmeScore}/100
                        </span>
                      </div>
                      {readmeChecked !== null && (
                        <p className="text-xs text-gray-400">{readmeChecked} of 6 README sections present</p>
                      )}
                      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <motion.div
                          className="h-full rounded-full"
                          style={{ background: readmeScore > 60 ? '#059669' : readmeScore >= 30 ? '#D97706' : '#DC2626' }}
                          initial={{ width: 0 }}
                          animate={{ width: `${readmeScore}%` }}
                          transition={{ duration: 1, ease: 'easeOut' }}
                        />
                      </div>
                    </div>

                    {/* Combined formula */}
                    <p className="text-xs text-gray-400 pt-1 border-t border-gray-100">
                      Final score = (0.70 × {fnDocScore}) + (0.30 × {readmeScore}) = <strong className="text-gray-600">{score}</strong>
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* README checklist */}
      <ReadmeChecklist readmeQuality={readmeQuality} readmeAssessment={readmeAssessment} />

      {/* Findings — missing docstrings / JSDoc */}
      {findings.length > 0 && (
        <div className="glass-card p-4">
          <div className="flex items-center gap-2 mb-3">
            <AlertCircle className="w-4 h-4 text-amber-400" />
            <h4 className="text-sm font-semibold text-gray-700">Missing Documentation ({findings.length})</h4>
          </div>
          <div className="space-y-2.5">
            {findings.map((f, i) => {
              const sev = String(f.severity || '').toLowerCase()
              const isCritical = sev === 'critical'
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04 }}
                  className={`p-3 rounded-lg border ${
                    isCritical ? 'bg-red-50/50 border-red-100' : 'bg-amber-50/50 border-amber-100'
                  }`}
                >
                  <div className="flex items-start gap-2.5">
                    <AlertTriangle className={`w-4 h-4 flex-shrink-0 mt-0.5 ${isCritical ? 'text-red-400' : 'text-amber-400'}`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-800 font-semibold">{f.title}</p>
                      {f.description && (
                        <p className="text-sm text-gray-600 mt-0.5 leading-relaxed">{f.description}</p>
                      )}
                      {/* Code location */}
                      <CodeLocation
                        filename={f.filename || f.file}
                        functionName={f.function_name || f.func}
                        line={f.line}
                      />
                      {/* Suggested doc */}
                      {f.suggested_doc && (
                        <div className="mt-2 p-2 bg-white/70 border border-gray-200 rounded-lg">
                          <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-0.5">Suggested docstring</p>
                          <p className="text-xs text-gray-600 italic">{f.suggested_doc}</p>
                        </div>
                      )}
                    </div>
                    <span className={`flex-shrink-0 text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                      isCritical ? 'severity-critical' : 'severity-warning'
                    }`}>
                      {f.severity}
                    </span>
                  </div>
                </motion.div>
              )
            })}
          </div>
        </div>
      )}

      {score === null && findings.length === 0 && !readmeQuality && (
        <EmptyState icon={BookOpen} message="No documentation data available." color="gray" />
      )}
    </div>
  )
}

// ── Empty state ──────────────────────────────────────────────────────────────
function EmptyState({ icon: Icon, message, color = 'gray' }) {
  const colors = {
    gray:    { bg: 'bg-gray-50',    text: 'text-gray-400',    icon: 'text-gray-300' },
    emerald: { bg: 'bg-emerald-50', text: 'text-emerald-600', icon: 'text-emerald-300' },
    indigo:  { bg: 'bg-indigo-50',  text: 'text-indigo-600',  icon: 'text-indigo-300' },
  }
  const c = colors[color] || colors.gray
  return (
    <div className={`${c.bg} rounded-xl p-10 flex flex-col items-center gap-3`}>
      <Icon className={`w-10 h-10 ${c.icon}`} />
      <p className={`text-sm font-medium ${c.text}`}>{message}</p>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function ResultsTabs({ report }) {
  const [activeTab, setActiveTab] = useState('bugs')

  const bugs    = report?.bugs            || []
  const vulns   = report?.vulnerabilities || []
  const fixes   = report?.fixes           || []

  // Prefer doc_report, fall back to doc_findings
  const docs    = report?.doc_report      || report?.doc_findings   || {}
  // Prefer quality_report, fall back to quality_issues
  const quality = report?.quality_report  || report?.quality_issues || {}

  // Merge fix data into each bug by matching on bug_title or filename+function_name
  const bugsWithFixes = bugs.map(bug => {
    const fix = fixes.find(f =>
      f.bug_title === bug.title ||
      (f.filename === bug.filename && f.function_name === bug.function_name)
    )
    if (!fix) return bug
    return {
      ...bug,
      // Use fixed_code from fixer (more complete than suggested_fix from detector)
      fixed_code:   fix.fixed_code   || bug.fixed_code,
      original_code: fix.original_code || bug.original_code,
      fix_mode:     fix.mode,
      status:       fix.status,
      attempts:     fix.attempts,
      verification: fix.verification,
      e2b_error:    fix.e2b_error,
    }
  })

  const counts = {
    bugs:     bugs.length,
    security: vulns.length,
    quality:  (quality?.issues || quality?.findings || []).length || null,
    docs:     (docs?.findings  || []).length || null,
  }

  return (
    <div className="glass-card p-0 overflow-hidden">
      {/* Tab bar */}
      <div className="flex border-b border-gray-100 bg-white/50 overflow-x-auto">
        {TABS.map((tab) => {
          const Icon     = tab.icon
          const isActive = activeTab === tab.id
          const count    = counts[tab.id]

          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`relative flex items-center gap-2 px-5 py-3.5 text-sm font-medium transition-colors whitespace-nowrap
                ${isActive ? 'text-indigo-600' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50/50'}
              `}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
              {count != null && count > 0 && (
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full
                  ${isActive ? 'bg-indigo-100 text-indigo-700' : 'bg-gray-100 text-gray-500'}
                `}>
                  {count}
                </span>
              )}
              {isActive && (
                <motion.div
                  layoutId="tab-indicator"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-600"
                  transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                />
              )}
            </button>
          )
        })}
      </div>

      {/* Tab content */}
      <div className="p-5">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
          >
            {activeTab === 'bugs' && (
              bugsWithFixes.length > 0
                ? <div className="space-y-3">
                    {bugsWithFixes.map((bug, i) => <BugCard key={i} bug={bug} index={i} />)}
                  </div>
                : <EmptyState icon={CheckCircle2} message="No bugs detected — clean code!" color="emerald" />
            )}

            {activeTab === 'security' && (
              vulns.length > 0
                ? <div className="space-y-3">
                    {vulns.map((v, i) => <VulnCard key={i} vuln={v} index={i} />)}
                  </div>
                : <EmptyState icon={Shield} message="No security vulnerabilities found." color="emerald" />
            )}

            {activeTab === 'quality' && <QualityTab qualityResult={quality} />}

            {activeTab === 'docs' && <DocsTab docResult={docs} />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}
