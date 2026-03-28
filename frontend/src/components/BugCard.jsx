import { AnimatePresence, motion } from 'framer-motion'
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Code2,
  FileCode,
  FolderOpen,
  Hash,
  Lightbulb,
  MinusCircle,
  Wrench,
  Zap,
} from 'lucide-react'
import { useState } from 'react'
import DiffViewer from './DiffViewer'

// ── Severity badge ───────────────────────────────────────────────────────────
function SeverityBadge({ severity }) {
  const s = String(severity || '').toLowerCase()
  if (s === 'critical' || s === 'high') {
    return (
      <span className="severity-critical flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full">
        <Zap className="w-3 h-3" /> {severity}
      </span>
    )
  }
  if (s === 'suggestion') {
    return (
      <span className="severity-info flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full">
        <Lightbulb className="w-3 h-3" /> suggestion
      </span>
    )
  }
  return (
    <span className="severity-warning flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full">
      <AlertTriangle className="w-3 h-3" /> {severity || 'warning'}
    </span>
  )
}

// ── Fix mode badge — distinguish execution vs AI review ──────────────────────
function FixModeBadge({ mode }) {
  if (!mode) return null
  const labels = {
    reflect:            { label: 'AI Reviewed',      cls: 'bg-violet-50 text-violet-700 border-violet-200' },
    execute_python:     { label: 'Python Execution',  cls: 'bg-blue-50 text-blue-700 border-blue-200' },
    execute_javascript: { label: 'JS Execution',      cls: 'bg-amber-50 text-amber-700 border-amber-200' },
  }
  const info = labels[mode] || { label: mode, cls: 'bg-gray-50 text-gray-600 border-gray-200' }
  return (
    <span className={`flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded border ${info.cls}`}>
      <Wrench className="w-3 h-3" /> {info.label}
    </span>
  )
}

// ── Code location block — full path clearly labeled ──────────────────────────
function CodeLocation({ filename, functionName, line }) {
  if (!filename && !functionName && !line) return null

  // Split path into folder + file
  const parts  = (filename || '').replace(/\\/g, '/').split('/')
  const file   = parts.pop() || filename
  const folder = parts.length > 0 ? parts.join('/') + '/' : ''

  return (
    <div className="mt-3 rounded-lg border border-indigo-100 bg-indigo-50/40 overflow-hidden">
      {/* Folder path */}
      {folder && (
        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-50 border-b border-indigo-100">
          <FolderOpen className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
          <span className="text-xs font-mono text-indigo-400 truncate">{folder}</span>
        </div>
      )}
      {/* File + function + line */}
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

// ── Beginner-friendly explanation generator ──────────────────────────────────
function getBeginnerExplanation(bug) {
  const title = String(bug?.title || '').toLowerCase()
  const desc  = String(bug?.description || '').toLowerCase()
  const mode  = bug?.fix_mode || bug?.mode || ''
  const fixed = bug?.fixed_code || bug?.suggested_fix || ''

  if (title.includes('null pointer') || title.includes('null pointer') || desc.includes('null') || desc.includes('undefined')) {
    return 'In programming, "null" or "undefined" means a variable exists but has no value yet — it\'s essentially an empty slot. The original code assumed that slot would always have something in it and tried to use it directly. When it turns out to be empty, the program crashes with an error like "Cannot read properties of null." This is one of the most common bugs in software. The fix adds a guard check that first asks "does this value exist?" before trying to use it — similar to checking whether a package has arrived before trying to open it. If the value is missing, the code now handles that situation gracefully instead of crashing.'
  }
  if (title.includes('dependency') || desc.includes('dependency')) {
    return 'React\'s useCallback and useEffect hooks are designed to run only when certain values (called "dependencies") change, to avoid unnecessary work. The dependency array at the end of the hook tells React which values to watch. When a value is used inside the hook but not listed in that array, React doesn\'t know to re-run the hook when that value changes — so the hook keeps using an old, stale copy of the data from when it first ran. This can cause the UI to show outdated information or behave inconsistently. The fix adds the missing value to the dependency array so React always re-runs the hook with the latest data.'
  }
  if (title.includes('recursion') || desc.includes('recursion') || desc.includes('re-render')) {
    return 'A function calling itself, or two functions calling each other, creates an infinite loop — the program never stops and eventually crashes with a "maximum call stack exceeded" error (or freezes the browser). In React, this often happens when a state update inside a component triggers a re-render, which triggers the same state update again. The fix introduces a condition that breaks the cycle — either a flag that marks when the function is already running and stops it from starting again, or a check that only updates state when the value has actually changed.'
  }
  if (title.includes('performance') || desc.includes('performance') || title.includes('too long')) {
    return 'This function is doing too many different things in one place, which creates two problems: it\'s slow because it has to complete every step before returning, and it\'s hard to understand because a reader has to hold all the logic in their head at once. Long, multi-purpose functions are also risky to change — a small edit in one part can accidentally break something in a completely different part of the same function. The fix splits the logic into smaller, focused functions where each one has a single clear purpose. This is easier to read, easier to test, and easier to maintain over time.'
  }
  if (title.includes('naming') || title.includes('variable')) {
    return 'A variable or function name that doesn\'t clearly describe its purpose makes code much harder to read and maintain. When you come back to your own code after a few weeks — or when someone else reads it for the first time — unclear names force you to read the entire surrounding code just to figure out what something holds or does. Research shows developers spend far more time reading code than writing it, so investing in clear names pays off quickly. The fix renames the variable or function to something descriptive that communicates its purpose at a glance, without needing to read the implementation.'
  }
  if (title.includes('input validation') || desc.includes('validat')) {
    return 'This code accepts data from an external source — a user form, URL parameter, or API request — and uses it directly without checking whether it\'s safe, in the right format, or within expected bounds. Unvalidated input is the root cause of many of the most serious security vulnerabilities, including SQL injection and cross-site scripting, as well as ordinary crashes from unexpected data types or values. The fix adds a validation step at the point where the data enters the system — it checks the type, length, format, and value range before anything else happens. Data that doesn\'t pass is rejected with a clear error message, and never reaches business logic or the database.'
  }
  if (title.includes('error') || desc.includes('error handling') || desc.includes('exception')) {
    return 'This code performs an operation that can fail — like a network request, database query, or file read — but doesn\'t handle the failure case. When something goes wrong, the error will propagate uncontrolled, either crashing the entire application or producing a confusing blank result. Some frameworks will also automatically send the raw error message (including internal file paths and stack traces) to the browser, which gives potential attackers information about your server\'s internals. The fix wraps the risky operation in a try/catch block so errors are intercepted before they cause damage — the full error is logged on the server for debugging, while the client receives only a safe, user-friendly message.'
  }
  if (mode === 'reflect') {
    return 'This fix was reviewed by an AI model that re-read both the original code and the proposed fix, then confirmed that the new version correctly addresses the problem described above. The review checks that the fix doesn\'t introduce new issues, that the logic is sound, and that the change achieves what was intended. The original code had a subtle flaw — the fix addresses it by improving how the code handles the specific scenario described in the bug title.'
  }
  if (desc) {
    return `The issue is: ${bug.description} When this bug is triggered, the program will behave incorrectly or crash instead of doing what was intended. The fix shown in the diff above corrects the logic directly — red lines (−) are the original buggy code that was removed, and green lines (+) are the corrected code that replaces it.`
  }
  return 'The fix corrects the logic shown in the diff above. Red lines (−) show the original buggy code that was removed, and green lines (+) show the corrected code that was added in its place. The goal is to make the program handle the problematic scenario correctly instead of failing.'
}

function BeginnerExplanation({ bug }) {
  const text = getBeginnerExplanation(bug)
  if (!text) return null
  return (
    <div className="mt-3 p-3 bg-blue-50/60 border border-blue-100 rounded-lg">
      <div className="flex items-start gap-2">
        <Lightbulb className="w-4 h-4 text-blue-500 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-xs font-semibold text-blue-700 uppercase tracking-wide mb-1.5">
            What does this fix do?
          </p>
          <p className="text-sm text-blue-900 leading-relaxed">{text}</p>
        </div>
      </div>
    </div>
  )
}

// ── E2B verification badge ───────────────────────────────────────────────────
function E2BVerificationBadge({ bug }) {
  const [showError, setShowError] = useState(false)
  const verification = String(bug?.verification || '').toLowerCase()
  const attempts     = bug?.attempts
  const fixMode      = bug?.fix_mode || bug?.mode
  const fixStatus    = bug?.status
  const e2bError     = bug?.e2b_error

  // reflect mode = AI validation, not sandbox execution
  const isReflect    = fixMode === 'reflect'
  const isVerified   = verification.includes('approved') || verification.includes('success')
  const couldNotFix  = fixStatus === 'could_not_fix'

  let label, badgeClass, icon
  if (couldNotFix) {
    label = 'Could Not Fix'
    badgeClass = 'bg-red-50 border-red-200'
    icon = <MinusCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
  } else if (isVerified && isReflect) {
    label = 'AI Validated'
    badgeClass = 'bg-violet-50 border-violet-200'
    icon = <CheckCircle2 className="w-4 h-4 text-violet-500 flex-shrink-0" />
  } else if (isVerified) {
    label = 'E2B Sandbox Verified'
    badgeClass = 'bg-emerald-50 border-emerald-200'
    icon = <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" />
  } else {
    label = 'Unverified'
    badgeClass = 'bg-gray-50 border-gray-200'
    icon = <MinusCircle className="w-4 h-4 text-gray-400 flex-shrink-0" />
  }

  return (
    <div className="mt-3 space-y-2">
      <div className={`flex items-center flex-wrap gap-2 px-3 py-2.5 rounded-lg border ${badgeClass}`}>
        {icon}
        <span className={`text-xs font-semibold ${
          couldNotFix ? 'text-red-600'
          : isVerified && isReflect ? 'text-violet-700'
          : isVerified ? 'text-emerald-700'
          : 'text-gray-500'
        }`}>
          {label}
        </span>

        {/* Only show FixModeBadge for non-reflect modes — reflect is already labelled "AI Validated" above */}
        {fixMode && !isReflect && <FixModeBadge mode={fixMode} />}

        {attempts != null && (
          <span className="text-[11px] text-gray-500 font-medium ml-auto">
            {couldNotFix
              ? `Failed after ${attempts} attempt${attempts > 1 ? 's' : ''}`
              : `Fixed on attempt ${attempts}/3`}
          </span>
        )}

        {e2bError && (
          <button
            onClick={() => setShowError(v => !v)}
            className="text-[11px] text-red-500 hover:text-red-700 font-medium ml-auto"
          >
            {showError ? '▲ Hide error' : '▼ Show E2B error'}
          </button>
        )}
      </div>

      {e2bError && showError && (
        <motion.pre
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          className="text-xs font-mono bg-gray-900 text-red-300 p-3 rounded-lg overflow-x-auto leading-relaxed"
        >
          {e2bError}
        </motion.pre>
      )}
    </div>
  )
}

// ── Main BugCard ─────────────────────────────────────────────────────────────
export default function BugCard({ bug, index }) {
  const [expanded, setExpanded] = useState(false)

  const hasCode      = !!(bug?.original_code || bug?.suggested_fix || bug?.fixed_code)
  const filename     = bug?.filename     || bug?.file     || ''
  const functionName = bug?.function_name || bug?.func     || ''
  const lineNumber   = bug?.line_number   || bug?.line
  const showE2B      = !!(bug?.verification || bug?.attempts || bug?.status)

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, type: 'spring', stiffness: 280, damping: 24 }}
      className="glass-card-hover overflow-hidden"
    >
      <div className="p-4">
        {/* Title row */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2.5 flex-1 min-w-0">
            <div className="flex-shrink-0 mt-0.5">
              <SeverityBadge severity={bug?.severity} />
            </div>
            <div className="min-w-0">
              <h3 className="text-sm font-semibold text-gray-800 leading-snug">
                {bug?.title || bug?.type || `Bug #${index + 1}`}
              </h3>
              {bug?.description && (
                <p className="text-sm text-gray-500 mt-1 leading-relaxed">
                  {bug.description}
                </p>
              )}
            </div>
          </div>

          {hasCode && (
            <button
              onClick={() => setExpanded(e => !e)}
              className="flex-shrink-0 flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 font-medium px-2.5 py-1.5 rounded-lg hover:bg-indigo-50 transition-colors"
            >
              <Code2 className="w-3.5 h-3.5" />
              {expanded ? 'Hide' : 'View'} Diff
              {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
          )}
        </div>

        {/* Code location — full path, function, line */}
        <CodeLocation filename={filename} functionName={functionName} line={lineNumber} />

        {/* Suggestion text when no code diff available */}
        {bug?.suggestion && !hasCode && (
          <p className="text-xs text-gray-600 mt-3 p-2.5 bg-gray-50 rounded-lg font-mono leading-relaxed">
            {bug.suggestion}
          </p>
        )}

        {/* E2B / AI verification row */}
        {showE2B && <E2BVerificationBadge bug={bug} />}
      </div>

      {/* Expandable diff + beginner explanation */}
      <AnimatePresence>
        {expanded && hasCode && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="px-4 pb-4 space-y-3"
          >
            <DiffViewer bug={bug} />
            <BeginnerExplanation bug={bug} />
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
