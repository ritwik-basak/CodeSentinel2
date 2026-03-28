import { motion } from 'framer-motion'
import { CheckCircle2, FileCode } from 'lucide-react'
import ReactDiffViewer from 'react-diff-viewer-continued'

const diffStyles = {
  variables: {
    light: {
      diffViewerBackground:    '#FAFAFA',
      addedBackground:         '#E6FFED',
      addedColor:              '#24292E',
      removedBackground:       '#FFEEF0',
      removedColor:            '#24292E',
      wordAddedBackground:     '#ACFFB0',
      wordRemovedBackground:   '#FFB3BA',
      addedGutterBackground:   '#CDFFD8',
      removedGutterBackground: '#FFDCE0',
      gutterBackground:        '#F7F8FA',
      gutterColor:             '#6E7781',
      codeFoldBackground:      '#F1F8FF',
      emptyLineBackground:     '#FAFBFC',
    },
  },
  line: { fontFamily: 'JetBrains Mono, monospace', fontSize: '13px' },
  gutter: { fontFamily: 'JetBrains Mono, monospace' },
}

export default function DiffViewer({ bug }) {
  const original = bug?.original_code || ''
  const fixed    = bug?.fixed_code    || bug?.suggested_fix || ''
  const filename = bug?.filename      || bug?.file          || 'unknown'
  const verified = String(bug?.verification || '').toLowerCase().includes('approved')

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.3, ease: 'easeInOut' }}
      className="overflow-hidden"
    >
      {/* Diff header bar */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-t-lg border-b-0">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5 text-xs font-medium text-red-500">
            <span className="w-2.5 h-2.5 rounded-full bg-red-400" />
            Original
          </span>
          <span className="flex items-center gap-1.5 text-xs font-medium text-emerald-600">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
            Fixed
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1 text-[11px] text-gray-500 font-mono bg-white border border-gray-200 px-2 py-0.5 rounded">
            <FileCode className="w-3 h-3" />
            {filename.split('/').pop()}
          </span>
          {verified && (
            <span className="flex items-center gap-1 text-[11px] text-emerald-700 font-medium bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded">
              <CheckCircle2 className="w-3 h-3" />
              E2B Verified ✓
            </span>
          )}
        </div>
      </div>

      {/* Diff body */}
      <div className="diff-container border border-gray-200 rounded-b-lg overflow-hidden">
        {original || fixed ? (
          <ReactDiffViewer
            oldValue={original}
            newValue={fixed}
            splitView={false}
            useDarkTheme={false}
            showDiffOnly={false}
            styles={diffStyles}
          />
        ) : (
          <div className="p-4 text-sm text-gray-400 italic font-mono bg-gray-50">
            No code diff available for this bug.
          </div>
        )}
      </div>
    </motion.div>
  )
}
