import { motion, useAnimation } from 'framer-motion'
import { useEffect } from 'react'

const SIZE    = 140
const STROKE  = 10
const RADIUS  = (SIZE - STROKE) / 2
const CIRCUM  = 2 * Math.PI * RADIUS

function scoreColor(score) {
  if (score >= 80) return { stroke: '#10B981', text: 'text-emerald-600', label: 'Healthy',  bg: 'from-emerald-50 to-emerald-100/50' }
  if (score >= 60) return { stroke: '#F59E0B', text: 'text-amber-500',   label: 'Fair',     bg: 'from-amber-50 to-amber-100/50' }
  return               { stroke: '#EF4444', text: 'text-red-500',     label: 'Critical', bg: 'from-red-50 to-red-100/50' }
}

export default function CircularScore({ score, label = 'Health Score' }) {
  const controls = useAnimation()
  const numScore = typeof score === 'number' ? score : 0
  const { stroke, text, label: verdict, bg } = scoreColor(numScore)

  const dashOffset = CIRCUM - (numScore / 100) * CIRCUM

  useEffect(() => {
    controls.start({
      strokeDashoffset: dashOffset,
      transition: { duration: 1.4, ease: [0.34, 1.56, 0.64, 1] },
    })
  }, [dashOffset, controls])

  return (
    <div className={`glass-card bg-gradient-to-br ${bg} p-6 flex flex-col items-center gap-3`}>
      <p className="text-sm font-medium text-gray-500">{label}</p>

      <div className="relative" style={{ width: SIZE, height: SIZE }}>
        <svg width={SIZE} height={SIZE} className="-rotate-90">
          {/* Track */}
          <circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={RADIUS}
            fill="none"
            stroke="rgba(0,0,0,0.07)"
            strokeWidth={STROKE}
          />
          {/* Progress arc */}
          <motion.circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={RADIUS}
            fill="none"
            stroke={stroke}
            strokeWidth={STROKE}
            strokeLinecap="round"
            strokeDasharray={CIRCUM}
            initial={{ strokeDashoffset: CIRCUM }}
            animate={controls}
            style={{ filter: `drop-shadow(0 0 6px ${stroke}66)` }}
          />
        </svg>

        {/* Center number */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <motion.span
            className={`text-3xl font-bold ${text} leading-none`}
            initial={{ opacity: 0, scale: 0.7 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.4, type: 'spring', stiffness: 260, damping: 20 }}
          >
            {numScore}
          </motion.span>
          <span className="text-xs text-gray-400 font-medium mt-0.5">/ 100</span>
        </div>
      </div>

      <motion.span
        className={`text-sm font-semibold ${text} px-3 py-1 rounded-full bg-white/60`}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.8 }}
      >
        {verdict}
      </motion.span>
    </div>
  )
}
