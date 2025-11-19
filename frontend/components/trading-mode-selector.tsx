interface TradingModeSelectorProps {
  mode: 'scalper' | 'normal' | 'aggressive' | 'longhold'
  setMode: (mode: 'scalper' | 'normal' | 'aggressive' | 'longhold') => void
}

export default function TradingModeSelector({ mode, setMode }: TradingModeSelectorProps) {
  const modes = [
    { id: 'scalper', label: 'Scalper', desc: 'Ultra-fast trades' },
    { id: 'normal', label: 'Normal', desc: 'Balanced approach' },
    { id: 'aggressive', label: 'Aggressive', desc: 'High risk/reward' },
    { id: 'longhold', label: 'Long Hold', desc: 'Position trading' },
  ]

  return (
    <div className="flex gap-2 flex-wrap">
      {modes.map((m) => (
        <button
          key={m.id}
          onClick={() => setMode(m.id as any)}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition flex flex-col items-start ${
            mode === m.id
              ? 'bg-purple-600 text-white'
              : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
          }`}
        >
          <span>{m.label}</span>
          <span className="text-xs opacity-75">{m.desc}</span>
        </button>
      ))}
    </div>
  )
}
