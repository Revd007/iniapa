interface AssetSelectorProps {
  assetClass: 'stocks' | 'forex' | 'crypto'
  setAssetClass: (asset: 'stocks' | 'forex' | 'crypto') => void
}

export default function AssetSelector({ assetClass, setAssetClass }: AssetSelectorProps) {
  const assets = [
    { id: 'crypto', label: 'Crypto Trading', emoji: '₿', active: true },
    { id: 'stocks', label: 'Stocks', emoji: '📈', active: false, soon: true },
    // Forex now active (using MT5 backend), no SOON badge
    { id: 'forex', label: 'Forex', emoji: '💱', active: true },
  ]

  return (
    <div className="flex gap-3">
      {assets.map((asset) => (
        <button
          key={asset.id}
          onClick={() => asset.active && setAssetClass(asset.id as any)}
          disabled={!asset.active}
          className={`px-6 py-3 rounded-lg font-semibold transition flex items-center gap-2 relative ${
            assetClass === asset.id && asset.active
              ? 'bg-gradient-to-r from-purple-600 to-blue-600 text-white shadow-lg'
              : asset.active
              ? 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              : 'bg-slate-800/50 text-slate-500 cursor-not-allowed'
          }`}
        >
          <span>{asset.emoji}</span>
          <span>{asset.label}</span>
          {asset.soon && (
            <span className="absolute -top-2 -right-2 text-xs px-2 py-0.5 bg-yellow-500 text-black rounded-full font-bold">
              SOON
            </span>
          )}
        </button>
      ))}
    </div>
  )
}
