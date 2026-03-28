import { motion } from 'framer-motion'
import { Bug, FileCode2, Braces, Heart } from 'lucide-react'

const CARD_DEFS = [
  {
    key:   'files',
    label: 'Total Files',
    icon:  FileCode2,
    color: 'indigo',
    bg:    'bg-indigo-50',
    iconBg:'bg-indigo-100',
    text:  'text-indigo-600',
  },
  {
    key:   'functions',
    label: 'Functions',
    icon:  Braces,
    color: 'violet',
    bg:    'bg-violet-50',
    iconBg:'bg-violet-100',
    text:  'text-violet-600',
  },
  {
    key:   'bugs',
    label: 'Bugs Found',
    icon:  Bug,
    color: 'rose',
    bg:    'bg-rose-50',
    iconBg:'bg-rose-100',
    text:  'text-rose-600',
  },
  {
    key:   'health',
    label: 'Health Score',
    icon:  Heart,
    color: 'dynamic',
    bg:    null, // computed below
    iconBg:null,
    text:  null,
  },
]

function healthColors(score) {
  if (score === null || score === undefined) {
    return { bg: 'bg-gray-50', iconBg: 'bg-gray-100', text: 'text-gray-500', val: '--' }
  }
  if (score >= 80) return { bg: 'bg-emerald-50', iconBg: 'bg-emerald-100', text: 'text-emerald-600' }
  if (score >= 60) return { bg: 'bg-amber-50',   iconBg: 'bg-amber-100',   text: 'text-amber-600' }
  return                  { bg: 'bg-red-50',     iconBg: 'bg-red-100',     text: 'text-red-600' }
}

const containerVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
}

const cardVariants = {
  hidden: { opacity: 0, y: 20, scale: 0.95 },
  show:   { opacity: 1, y: 0,  scale: 1, transition: { type: 'spring', stiffness: 300, damping: 24 } },
}

export default function StatCards({ stats }) {
  // stats: { files, functions, bugs, health }
  const s = stats || {}
  const hc = healthColors(s.health)

  const values = {
    files:     s.files     ?? '—',
    functions: s.functions ?? '—',
    bugs:      s.bugs      ?? '—',
    health:    s.health    != null ? `${s.health}/100` : '—',
  }

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="show"
      className="grid grid-cols-2 gap-3"
    >
      {CARD_DEFS.map((card) => {
        const isDynamic = card.color === 'dynamic'
        const bg     = isDynamic ? hc.bg     : card.bg
        const iconBg = isDynamic ? hc.iconBg : card.iconBg
        const text   = isDynamic ? hc.text   : card.text
        const Icon   = card.icon

        return (
          <motion.div
            key={card.key}
            variants={cardVariants}
            className={`glass-card p-4 ${bg}`}
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-medium text-gray-500 mb-1">{card.label}</p>
                <p className={`text-2xl font-bold ${text}`}>
                  {values[card.key]}
                </p>
              </div>
              <div className={`${iconBg} p-2.5 rounded-xl`}>
                <Icon className={`w-5 h-5 ${text}`} />
              </div>
            </div>
          </motion.div>
        )
      })}
    </motion.div>
  )
}
