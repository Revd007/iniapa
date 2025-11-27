'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { ChartData } from '@/lib/api'

interface CandlestickChartProps {
  data: ChartData[]
}

/**
 * Professional Candlestick Chart Component
 * 
 * Features:
 * - Real-time price visualization with candlestick patterns
 * - Interactive zoom and pan controls
 * - Moving averages (MA20, MA50)
 * - Volume bars
 * - Crosshair with OHLCV tooltip
 * - Responsive design
 * 
 * Performance optimizations:
 * - Efficient canvas rendering
 * - Debounced resize handling
 * - Memoized calculation functions
 */
export default function CandlestickChart({ data }: CandlestickChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const animationFrameRef = useRef<number | null>(null)
  
  // Chart interaction state
  const [offset, setOffset] = useState(0)
  const [zoom, setZoom] = useState(1)
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, offset: 0 })
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null)
  const [error, setError] = useState<string | null>(null)

  /**
   * Setup canvas and handle window resize
   * Uses debouncing to prevent excessive redraws during resize
   */
  useEffect(() => {
    let resizeTimeout: NodeJS.Timeout

    const handleResize = () => {
      clearTimeout(resizeTimeout)
      resizeTimeout = setTimeout(() => {
        if (containerRef.current && canvasRef.current) {
          const rect = containerRef.current.getBoundingClientRect()
          const dpr = window.devicePixelRatio || 1
          
          // Set canvas size with device pixel ratio for crisp rendering
          canvasRef.current.width = rect.width * dpr
          canvasRef.current.height = rect.height * dpr
          canvasRef.current.style.width = `${rect.width}px`
          canvasRef.current.style.height = `${rect.height}px`
          
          // Scale context for high-DPI displays
          const ctx = canvasRef.current.getContext('2d')
          if (ctx) {
            ctx.scale(dpr, dpr)
          }
          
          drawChart()
        }
      }, 100) // Debounce resize events
    }

    try {
      handleResize()
      window.addEventListener('resize', handleResize)
    } catch (err) {
      setError('Failed to initialize chart')
      console.error('Chart initialization error:', err)
    }

    return () => {
      clearTimeout(resizeTimeout)
      window.removeEventListener('resize', handleResize)
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current)
      }
    }
  }, [data, offset, zoom, hoveredIndex, mousePos])

  /**
   * Main drawing function - renders entire chart
   * 
   * Follows TradingView style with professional colors and layout
   * Optimized for performance with efficient canvas operations
   */
  const drawChart = useCallback(() => {
    if (!canvasRef.current || !containerRef.current) return
    
    // Validation: Check if data is available and valid
    if (!data || data.length === 0) {
      const canvas = canvasRef.current
      const ctx = canvas.getContext('2d')
      if (ctx) {
        const rect = containerRef.current.getBoundingClientRect()
        ctx.fillStyle = '#0f1419'
        ctx.fillRect(0, 0, rect.width, rect.height)
        ctx.fillStyle = '#848e9c'
        ctx.font = '14px sans-serif'
        ctx.textAlign = 'center'
        ctx.fillText('No chart data available', rect.width / 2, rect.height / 2)
      }
      return
    }

    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d', { 
      alpha: false,
      desynchronized: true // Hint for better performance
    })
    if (!ctx) return

    // Use actual display size, not scaled canvas size
    const rect = containerRef.current.getBoundingClientRect()
    const width = rect.width
    const height = rect.height

    // === Clear canvas dengan dark background ala TradingView ===
    ctx.fillStyle = '#0f1419'
    ctx.fillRect(0, 0, width, height)

    // === Calculate visible data range with bounds checking ===
    const candlesPerView = Math.max(30, Math.floor(100 / zoom))
    const endIndex = Math.min(data.length, data.length - offset)
    const startIndex = Math.max(0, endIndex - candlesPerView)
    const visibleData = data.slice(startIndex, endIndex)

    // Safety check for empty visible data
    if (!visibleData || visibleData.length === 0) {
      ctx.fillStyle = '#848e9c'
      ctx.font = '12px sans-serif'
      ctx.textAlign = 'center'
      ctx.fillText('No data in current view', width / 2, height / 2)
      return
    }

    // === Chart margins (untuk axes dan labels) ===
    const marginLeft = 60
    const marginRight = 80
    const marginTop = 30
    const marginBottom = 70
    const chartWidth = width - marginLeft - marginRight
    const chartHeight = height - marginTop - marginBottom

    // === Calculate price range with padding and validation ===
    const prices = visibleData.flatMap(d => [d.high || 0, d.low || 0]).filter(p => p > 0)
    if (prices.length === 0) {
      ctx.fillStyle = '#848e9c'
      ctx.font = '12px sans-serif'
      ctx.textAlign = 'center'
      ctx.fillText('Invalid price data', width / 2, height / 2)
      return
    }
    
    const maxPrice = Math.max(...prices)
    const minPrice = Math.min(...prices)
    const priceRange = Math.max(maxPrice - minPrice, 0.01) // Prevent division by zero
    const padding = priceRange * 0.08 // 8% padding

    // Helper: convert price to Y coordinate
    const priceToY = (price: number) => {
      return marginTop + chartHeight * (1 - ((price - minPrice + padding) / (priceRange + 2 * padding)))
    }

    // Helper: convert index to X coordinate
    const candleWidth = chartWidth / candlesPerView
    const indexToX = (index: number) => {
      return marginLeft + (index - startIndex) * candleWidth
    }

    // === Draw grid (horizontal price levels) ===
    ctx.strokeStyle = '#1e2329'
    ctx.lineWidth = 1
    const priceSteps = 10
    for (let i = 0; i <= priceSteps; i++) {
      const y = marginTop + (chartHeight / priceSteps) * i
      ctx.beginPath()
      ctx.moveTo(marginLeft, y)
      ctx.lineTo(marginLeft + chartWidth, y)
      ctx.stroke()

      // Price labels (right side)
      const price = maxPrice + padding - ((priceRange + 2 * padding) / priceSteps) * i
      ctx.fillStyle = '#848e9c'
      ctx.font = '11px "SF Pro Text", -apple-system, system-ui, sans-serif'
      ctx.textAlign = 'left'
      ctx.fillText(price.toFixed(price > 100 ? 2 : 4), marginLeft + chartWidth + 8, y + 4)
    }

    // === Draw vertical grid (time intervals) ===
    const timeSteps = Math.min(10, Math.floor(visibleData.length / 5))
    const timeInterval = Math.max(1, Math.floor(visibleData.length / timeSteps))
    for (let i = 0; i < visibleData.length; i += timeInterval) {
      const x = indexToX(i + startIndex)
      ctx.beginPath()
      ctx.moveTo(x, marginTop)
      ctx.lineTo(x, marginTop + chartHeight)
      ctx.stroke()

      // Time labels (bottom)
      const timestamp = visibleData[i].time
      const date = new Date(timestamp)
      const timeLabel = date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
      ctx.fillStyle = '#848e9c'
      ctx.font = '10px "SF Pro Text", -apple-system, system-ui, sans-serif'
      ctx.textAlign = 'center'
      ctx.fillText(timeLabel, x, marginTop + chartHeight + 20)
    }

    // === Draw MA lines (Moving Averages) ===
    // MA20 - Blue
    ctx.strokeStyle = '#2962ff'
    ctx.lineWidth = 1.5
    ctx.beginPath()
    let ma20Started = false
    for (let i = 0; i < visibleData.length; i++) {
      if (visibleData[i].ma20) {
        const x = indexToX(i + startIndex) + candleWidth / 2
        const y = priceToY(visibleData[i].ma20!)
        if (!ma20Started) {
          ctx.moveTo(x, y)
          ma20Started = true
        } else {
          ctx.lineTo(x, y)
        }
      }
    }
    ctx.stroke()

    // MA50 - Orange
    ctx.strokeStyle = '#ff9800'
    ctx.lineWidth = 1.5
    ctx.beginPath()
    let ma50Started = false
    for (let i = 0; i < visibleData.length; i++) {
      if (visibleData[i].ma50) {
        const x = indexToX(i + startIndex) + candleWidth / 2
        const y = priceToY(visibleData[i].ma50!)
        if (!ma50Started) {
          ctx.moveTo(x, y)
          ma50Started = true
        } else {
          ctx.lineTo(x, y)
        }
      }
    }
    ctx.stroke()

    // === Draw candlesticks ===
    visibleData.forEach((candle, i) => {
      const x = indexToX(i + startIndex)
      const openY = priceToY(candle.open)
      const closeY = priceToY(candle.close)
      const highY = priceToY(candle.high)
      const lowY = priceToY(candle.low)

      const isBullish = candle.close >= candle.open
      const bodyHeight = Math.abs(closeY - openY)
      const bodyTop = Math.min(openY, closeY)
      
      // Warna ala TradingView
      const bullishColor = '#26a69a' // Teal green
      const bearishColor = '#ef5350' // Red
      const wickColor = isBullish ? '#26a69a' : '#ef5350'

      // Optimal candle width (60% of available space, min 2px, max 12px)
      const bodyWidth = Math.min(12, Math.max(2, candleWidth * 0.6))
      const centerX = x + candleWidth / 2

      // Draw wick (thin line)
      ctx.strokeStyle = wickColor
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(centerX, highY)
      ctx.lineTo(centerX, lowY)
      ctx.stroke()

      // Draw body (candlestick)
      if (bodyHeight < 1) {
        // Doji: body sangat kecil, gambar garis horizontal
        ctx.strokeStyle = isBullish ? bullishColor : bearishColor
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.moveTo(centerX - bodyWidth / 2, bodyTop)
        ctx.lineTo(centerX + bodyWidth / 2, bodyTop)
        ctx.stroke()
      } else {
        // Normal candle
        if (isBullish) {
          // Bullish: hollow (border only)
          ctx.strokeStyle = bullishColor
          ctx.lineWidth = 1.5
          ctx.strokeRect(centerX - bodyWidth / 2, bodyTop, bodyWidth, bodyHeight)
        } else {
          // Bearish: filled
          ctx.fillStyle = bearishColor
          ctx.fillRect(centerX - bodyWidth / 2, bodyTop, bodyWidth, bodyHeight)
        }
      }
    })

    // === Draw crosshair dan tooltip saat hover ===
    if (hoveredIndex !== null && mousePos) {
      const hoveredCandle = visibleData[hoveredIndex]
      if (hoveredCandle) {
        // Crosshair lines
        ctx.strokeStyle = '#787b86'
        ctx.lineWidth = 1
        ctx.setLineDash([4, 4])

        // Vertical line
        ctx.beginPath()
        ctx.moveTo(mousePos.x, marginTop)
        ctx.lineTo(mousePos.x, marginTop + chartHeight)
        ctx.stroke()

        // Horizontal line
        ctx.beginPath()
        ctx.moveTo(marginLeft, mousePos.y)
        ctx.lineTo(marginLeft + chartWidth, mousePos.y)
        ctx.stroke()

        ctx.setLineDash([])

        // === Tooltip box (OHLCV data) ===
        const tooltipX = 10
        const tooltipY = 10
        const tooltipWidth = 200
        const tooltipHeight = 120

        // Tooltip background
        ctx.fillStyle = 'rgba(15, 20, 25, 0.95)'
        ctx.strokeStyle = '#2a2e39'
        ctx.lineWidth = 1
        ctx.fillRect(tooltipX, tooltipY, tooltipWidth, tooltipHeight)
        ctx.strokeRect(tooltipX, tooltipY, tooltipWidth, tooltipHeight)

        // Tooltip content
        ctx.font = '11px "SF Pro Text", -apple-system, system-ui, sans-serif'
        ctx.textAlign = 'left'
        let lineY = tooltipY + 18

        // Time
        const date = new Date(hoveredCandle.time)
        ctx.fillStyle = '#848e9c'
        ctx.fillText(
          date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
          }),
          tooltipX + 10,
          lineY
        )
        lineY += 18

        // OHLC with labels
        const labels = [
          { label: 'O', value: hoveredCandle.open, color: '#848e9c' },
          { label: 'H', value: hoveredCandle.high, color: '#26a69a' },
          { label: 'L', value: hoveredCandle.low, color: '#ef5350' },
          { label: 'C', value: hoveredCandle.close, color: hoveredCandle.close >= hoveredCandle.open ? '#26a69a' : '#ef5350' }
        ]

        labels.forEach(({ label, value, color }) => {
          ctx.fillStyle = '#848e9c'
          ctx.fillText(label + ':', tooltipX + 10, lineY)
          ctx.fillStyle = color
          ctx.fillText(value.toFixed(value > 100 ? 2 : 4), tooltipX + 30, lineY)
          lineY += 16
        })

        // Volume
        ctx.fillStyle = '#848e9c'
        ctx.fillText('Vol:', tooltipX + 10, lineY)
        ctx.fillStyle = '#ffffff'
        ctx.fillText(hoveredCandle.volume.toFixed(2), tooltipX + 40, lineY)
      }
    }

    // === Draw volume bars at bottom ===
    const volumeHeight = 50
    const volumeTop = marginTop + chartHeight + 30
    const volumes = visibleData.map(d => d.volume || 0).filter(v => v > 0)
    const maxVolume = volumes.length > 0 ? Math.max(...volumes) : 1 // Prevent division by zero

    visibleData.forEach((candle, i) => {
      if (!candle.volume || candle.volume <= 0) return
      
      const x = indexToX(i + startIndex)
      const barHeight = Math.min((candle.volume / maxVolume) * volumeHeight, volumeHeight)
      const centerX = x + candleWidth / 2
      const barWidth = Math.min(10, candleWidth * 0.6)

      const isBullish = candle.close >= candle.open
      ctx.fillStyle = isBullish ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)'
      ctx.fillRect(centerX - barWidth / 2, volumeTop + volumeHeight - barHeight, barWidth, barHeight)
    })
  }, [data, offset, zoom, hoveredIndex, mousePos])

  // === Event handlers untuk interaksi ===
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    setIsDragging(true)
    setDragStart({ x: e.clientX, offset })
  }

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!canvasRef.current || !containerRef.current) return

    const rect = canvasRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    setMousePos({ x, y })

    // Calculate which candle is being hovered
    const marginLeft = 60
    const chartWidth = rect.width - 60 - 80
    const candlesPerView = Math.max(30, Math.floor(100 / zoom))
    const candleWidth = chartWidth / candlesPerView
    const endIndex = data.length - offset
    const startIndex = Math.max(0, endIndex - candlesPerView)

    if (x >= marginLeft && x <= marginLeft + chartWidth) {
      const relativeX = x - marginLeft
      const hoveredIdx = Math.floor(relativeX / candleWidth)
      if (hoveredIdx >= 0 && hoveredIdx < endIndex - startIndex) {
        setHoveredIndex(hoveredIdx)
      } else {
        setHoveredIndex(null)
      }
    } else {
      setHoveredIndex(null)
    }

    // Pan chart jika dragging
    if (isDragging) {
      const delta = Math.floor((dragStart.x - e.clientX) / (candleWidth * zoom))
      const newOffset = Math.max(0, Math.min(data.length - 10, dragStart.offset + delta))
      setOffset(newOffset)
    }
  }

  const handleMouseUp = () => {
    setIsDragging(false)
  }

  const handleMouseLeave = () => {
    setIsDragging(false)
    setHoveredIndex(null)
    setMousePos(null)
  }

  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    // Zoom in/out dengan mouse wheel
    const zoomSpeed = 0.1
    const newZoom = e.deltaY < 0 ? zoom * (1 + zoomSpeed) : zoom * (1 - zoomSpeed)
    setZoom(Math.max(0.5, Math.min(5, newZoom)))
  }

  // === Zoom controls ===
  const zoomIn = () => setZoom(Math.min(5, zoom * 1.2))
  const zoomOut = () => setZoom(Math.max(0.5, zoom / 1.2))
  const resetZoom = () => {
    setZoom(1)
    setOffset(0)
  }

  // Show error message if chart failed to initialize
  if (error) {
    return (
      <div className="relative w-full h-full flex items-center justify-center bg-slate-900">
        <div className="text-center">
          <p className="text-red-400 font-semibold mb-2">⚠️ Chart Error</p>
          <p className="text-slate-400 text-sm">{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div ref={containerRef} className="relative w-full h-full">
      <canvas
        ref={canvasRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
        onWheel={handleWheel}
        className="w-full h-full cursor-crosshair"
      />
      
      {/* Zoom controls - floating bottom-right */}
      <div className="absolute bottom-2 right-2 flex gap-1 bg-slate-900/80 border border-slate-700 rounded p-1">
        <button
          onClick={zoomIn}
          className="w-6 h-6 flex items-center justify-center text-slate-300 hover:text-white hover:bg-slate-800 rounded text-sm"
          title="Zoom In"
        >
          +
        </button>
        <button
          onClick={zoomOut}
          className="w-6 h-6 flex items-center justify-center text-slate-300 hover:text-white hover:bg-slate-800 rounded text-sm"
          title="Zoom Out"
        >
          −
        </button>
        <button
          onClick={resetZoom}
          className="px-2 h-6 flex items-center justify-center text-slate-300 hover:text-white hover:bg-slate-800 rounded text-[10px]"
          title="Reset View"
        >
          Reset
        </button>
      </div>
    </div>
  )
}
