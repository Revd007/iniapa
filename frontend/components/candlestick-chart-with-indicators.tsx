'use client'

import { useEffect, useRef, useState } from 'react'
import { ChartData } from '@/lib/api'

interface CandlestickChartProps {
  data: ChartData[]
}

export default function CandlestickChartWithIndicators({ data }: CandlestickChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  
  // State untuk zoom dan pan
  const [offset, setOffset] = useState(0)
  const [zoom, setZoom] = useState(1)
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, offset: 0 })
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null)

  useEffect(() => {
    const handleResize = () => {
      if (containerRef.current && canvasRef.current) {
        const rect = containerRef.current.getBoundingClientRect()
        canvasRef.current.width = rect.width
        canvasRef.current.height = rect.height
        drawChart()
      }
    }

    handleResize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [data, offset, zoom, hoveredIndex, mousePos])

  /**
   * Main drawing function dengan 3 panels: Main Chart, RSI, MACD
   */
  const drawChart = () => {
    if (!canvasRef.current || !containerRef.current || data.length === 0) return

    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d', { alpha: false })
    if (!ctx) return

    const width = canvas.width
    const height = canvas.height

    // === Clear canvas ===
    ctx.fillStyle = '#0a0e14'
    ctx.fillRect(0, 0, width, height)

    // === Calculate visible data ===
    // Adaptive display - handle up to 1000 candles smoothly
    // Show optimal amount based on total data available
    let baseCandles: number
    if (data.length >= 800) {
      // Banyak data (800-1000): show 15-20% untuk clarity
      baseCandles = Math.min(200, Math.floor(data.length * 0.18))
    } else if (data.length >= 500) {
      // Medium data (500-800): show 25-30%
      baseCandles = Math.floor(data.length * 0.28)
    } else if (data.length >= 200) {
      // Normal data (200-500): show 40-50%
      baseCandles = Math.floor(data.length * 0.45)
    } else {
      // Sedikit data (<200): show 70-80%
      baseCandles = Math.floor(data.length * 0.75)
    }
    
    const candlesPerView = Math.max(50, Math.min(data.length, Math.floor(baseCandles / zoom)))
    const endIndex = data.length - offset
    const startIndex = Math.max(0, endIndex - candlesPerView)
    const visibleData = data.slice(startIndex, endIndex)

    if (visibleData.length === 0) return

    // === Layout: 3 panels stacked vertically ===
    const marginLeft = 60
    const marginRight = 80
    const marginTop = 10
    const marginBottom = 30
    const panelGap = 5

    const totalHeight = height - marginTop - marginBottom
    const mainPanelHeight = Math.floor(totalHeight * 0.60) // 60% untuk main chart
    const rsiPanelHeight = Math.floor(totalHeight * 0.20)  // 20% untuk RSI
    const macdPanelHeight = Math.floor(totalHeight * 0.20) // 20% untuk MACD

    const chartWidth = width - marginLeft - marginRight

    // Panel positions
    const mainPanelTop = marginTop
    const rsiPanelTop = mainPanelTop + mainPanelHeight + panelGap
    const macdPanelTop = rsiPanelTop + rsiPanelHeight + panelGap

    // Helper: convert index to X coordinate
    const candleWidth = chartWidth / candlesPerView
    const indexToX = (index: number) => {
      return marginLeft + (index - startIndex) * candleWidth
    }

    // === PANEL 1: MAIN CHART (Price + MA lines) ===
    drawMainPanel(ctx, visibleData, startIndex, {
      left: marginLeft,
      right: marginLeft + chartWidth,
      top: mainPanelTop,
      height: mainPanelHeight,
      width: chartWidth,
      candleWidth,
      indexToX
    })

    // === PANEL 2: RSI ===
    drawRSIPanel(ctx, visibleData, startIndex, {
      left: marginLeft,
      right: marginLeft + chartWidth,
      top: rsiPanelTop,
      height: rsiPanelHeight,
      width: chartWidth,
      candleWidth,
      indexToX
    })

    // === PANEL 3: MACD ===
    drawMACDPanel(ctx, visibleData, startIndex, {
      left: marginLeft,
      right: marginLeft + chartWidth,
      top: macdPanelTop,
      height: macdPanelHeight,
      width: chartWidth,
      candleWidth,
      indexToX
    })

    // === Draw crosshair & tooltip (over all panels) ===
    if (hoveredIndex !== null && mousePos) {
      drawCrosshair(ctx, visibleData[hoveredIndex], mousePos, marginLeft, marginRight, chartWidth, height)
    }
  }

  /**
   * Draw main price panel dengan candlesticks dan MA lines
   */
  const drawMainPanel = (ctx: CanvasRenderingContext2D, visibleData: ChartData[], startIndex: number, layout: any) => {
    const { left, right, top, height, width, candleWidth, indexToX } = layout

    // Price range
    const prices = visibleData.flatMap(d => [d.high, d.low])
    const maxPrice = Math.max(...prices)
    const minPrice = Math.min(...prices)
    const priceRange = maxPrice - minPrice
    const padding = priceRange * 0.05

    const priceToY = (price: number) => {
      return top + height * (1 - ((price - minPrice + padding) / (priceRange + 2 * padding)))
    }

    // Draw grid
    ctx.strokeStyle = '#1a1f2a'
    ctx.lineWidth = 1
    for (let i = 0; i <= 8; i++) {
      const y = top + (height / 8) * i
      ctx.beginPath()
      ctx.moveTo(left, y)
      ctx.lineTo(right, y)
      ctx.stroke()

      // Price label
      const price = maxPrice + padding - ((priceRange + 2 * padding) / 8) * i
      ctx.fillStyle = '#6b7280'
      ctx.font = '10px system-ui'
      ctx.textAlign = 'left'
      ctx.fillText(price.toFixed(price > 100 ? 2 : 4), right + 5, y + 3)
    }

    // Panel label
    ctx.fillStyle = '#9ca3af'
    ctx.font = 'bold 11px system-ui'
    ctx.textAlign = 'left'
    ctx.fillText('Price', left + 5, top + 15)

    // Draw MA lines with TradingView colors
    // MA20 - Blue/Purple (TradingView style)
    ctx.strokeStyle = '#2962FF'
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

    // MA50 - Orange (TradingView style)
    ctx.strokeStyle = '#FF6D00'
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

    // Draw candlesticks
    visibleData.forEach((candle, i) => {
      const x = indexToX(i + startIndex)
      const openY = priceToY(candle.open)
      const closeY = priceToY(candle.close)
      const highY = priceToY(candle.high)
      const lowY = priceToY(candle.low)

      const isBullish = candle.close >= candle.open
      const bodyHeight = Math.abs(closeY - openY)
      const bodyTop = Math.min(openY, closeY)
      
      const bullishColor = '#26a69a' // Teal green (TradingView style)
      const bearishColor = '#ef5350' // Red (TradingView style)

      // Calculate body width - TradingView style (80% of candle space, min 3px, max 12px)
      const bodyWidth = Math.min(12, Math.max(3, candleWidth * 0.8))
      const centerX = x + candleWidth / 2

      // Make body more visible: minimum height 2px for very small price changes
      const minBodyHeight = 2
      const adjustedBodyHeight = Math.max(minBodyHeight, bodyHeight)
      const adjustedBodyTop = bodyHeight < minBodyHeight ? bodyTop - (minBodyHeight - bodyHeight) / 2 : bodyTop

      // Wick (thin line)
      ctx.strokeStyle = isBullish ? bullishColor : bearishColor
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(centerX, highY)
      ctx.lineTo(centerX, lowY)
      ctx.stroke()

      // Body - Always draw solid body for clarity
      if (adjustedBodyHeight < 1.5) {
        // Very small body / Doji - draw as horizontal line (thicker)
        ctx.strokeStyle = isBullish ? bullishColor : bearishColor
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.moveTo(centerX - bodyWidth / 2, bodyTop)
        ctx.lineTo(centerX + bodyWidth / 2, bodyTop)
        ctx.stroke()
      } else {
        if (isBullish) {
          // Bullish: filled with green (TradingView 2023+ style)
          ctx.fillStyle = bullishColor
          ctx.fillRect(centerX - bodyWidth / 2, adjustedBodyTop, bodyWidth, adjustedBodyHeight)
          // Optional: add subtle border for definition
          ctx.strokeStyle = bullishColor
          ctx.lineWidth = 1
          ctx.strokeRect(centerX - bodyWidth / 2, adjustedBodyTop, bodyWidth, adjustedBodyHeight)
        } else {
          // Bearish: filled with red
          ctx.fillStyle = bearishColor
          ctx.fillRect(centerX - bodyWidth / 2, adjustedBodyTop, bodyWidth, adjustedBodyHeight)
        }
      }
    })
  }

  /**
   * Draw RSI panel
   */
  const drawRSIPanel = (ctx: CanvasRenderingContext2D, visibleData: ChartData[], startIndex: number, layout: any) => {
    const { left, right, top, height, width, candleWidth, indexToX } = layout

    // RSI range: 0-100
    const rsiToY = (rsi: number) => {
      return top + height * (1 - rsi / 100)
    }

    // Background + grid
    ctx.fillStyle = '#0d1117'
    ctx.fillRect(left, top, width, height)

    ctx.strokeStyle = '#1a1f2a'
    ctx.lineWidth = 1

    // Horizontal lines at 30, 50, 70
    ;[30, 50, 70].forEach(level => {
      const y = rsiToY(level)
      ctx.beginPath()
      ctx.moveTo(left, y)
      ctx.lineTo(right, y)
      ctx.stroke()

      // Label
      ctx.fillStyle = level === 70 ? '#ef4444' : level === 30 ? '#10b981' : '#6b7280'
      ctx.font = '9px system-ui'
      ctx.textAlign = 'left'
      ctx.fillText(level.toString(), right + 5, y + 3)
    })

    // Panel label
    ctx.fillStyle = '#9ca3af'
    ctx.font = 'bold 11px system-ui'
    ctx.textAlign = 'left'
    ctx.fillText('RSI (14)', left + 5, top + 15)

    // Draw RSI line (TradingView purple)
    ctx.strokeStyle = '#7E57C2' // Purple (TradingView style)
    ctx.lineWidth = 2.5
    ctx.beginPath()
    let rsiStarted = false

    for (let i = 0; i < visibleData.length; i++) {
      if (visibleData[i].rsi !== undefined && visibleData[i].rsi !== null) {
        const x = indexToX(i + startIndex) + candleWidth / 2
        const y = rsiToY(visibleData[i].rsi!)
        if (!rsiStarted) {
          ctx.moveTo(x, y)
          rsiStarted = true
        } else {
          ctx.lineTo(x, y)
        }
      }
    }
    ctx.stroke()

    // Fill area under RSI line (gradient) - TradingView style
    if (rsiStarted) {
      const gradient = ctx.createLinearGradient(0, top, 0, top + height)
      gradient.addColorStop(0, 'rgba(126, 87, 194, 0.25)')
      gradient.addColorStop(1, 'rgba(126, 87, 194, 0.0)')
      ctx.fillStyle = gradient
      
      ctx.beginPath()
      for (let i = 0; i < visibleData.length; i++) {
        if (visibleData[i].rsi !== undefined && visibleData[i].rsi !== null) {
          const x = indexToX(i + startIndex) + candleWidth / 2
          const y = rsiToY(visibleData[i].rsi!)
          if (i === 0) ctx.moveTo(x, y)
          else ctx.lineTo(x, y)
        }
      }
      // Close path to bottom
      const lastX = indexToX(visibleData.length - 1 + startIndex) + candleWidth / 2
      ctx.lineTo(lastX, top + height)
      ctx.lineTo(indexToX(startIndex) + candleWidth / 2, top + height)
      ctx.closePath()
      ctx.fill()
    }
  }

  /**
   * Draw MACD panel
   */
  const drawMACDPanel = (ctx: CanvasRenderingContext2D, visibleData: ChartData[], startIndex: number, layout: any) => {
    const { left, right, top, height, width, candleWidth, indexToX } = layout

    // Find MACD range
    const macdValues = visibleData.flatMap(d => [
      d.macd ?? 0,
      d.macd_signal ?? 0,
      d.macd_histogram ?? 0
    ])
    const maxMacd = Math.max(...macdValues, 10)
    const minMacd = Math.min(...macdValues, -10)
    const macdRange = maxMacd - minMacd

    const macdToY = (value: number) => {
      return top + height * (1 - ((value - minMacd) / macdRange))
    }

    // Background + grid
    ctx.fillStyle = '#0d1117'
    ctx.fillRect(left, top, width, height)

    ctx.strokeStyle = '#1a1f2a'
    ctx.lineWidth = 1

    // Zero line
    const zeroY = macdToY(0)
    ctx.strokeStyle = '#374151'
    ctx.beginPath()
    ctx.moveTo(left, zeroY)
    ctx.lineTo(right, zeroY)
    ctx.stroke()

    // Panel label
    ctx.fillStyle = '#9ca3af'
    ctx.font = 'bold 11px system-ui'
    ctx.textAlign = 'left'
    ctx.fillText('MACD (12,26,9)', left + 5, top + 15)

    // Draw histogram (background)
    visibleData.forEach((candle, i) => {
      if (candle.macd_histogram !== undefined && candle.macd_histogram !== null) {
        const x = indexToX(i + startIndex)
        const barHeight = Math.abs(macdToY(candle.macd_histogram) - zeroY)
        const barTop = candle.macd_histogram >= 0 ? macdToY(candle.macd_histogram) : zeroY
        const barWidth = Math.max(1, candleWidth * 0.6)
        const centerX = x + candleWidth / 2

        // TradingView style histogram colors
        ctx.fillStyle = candle.macd_histogram >= 0 
          ? 'rgba(38, 166, 154, 0.5)'  // Teal green
          : 'rgba(239, 83, 80, 0.5)'   // Red
        ctx.fillRect(centerX - barWidth / 2, barTop, barWidth, barHeight)
      }
    })

    // Draw MACD line (TradingView style)
    ctx.strokeStyle = '#2962FF' // Blue
    ctx.lineWidth = 1.8
    ctx.beginPath()
    let macdStarted = false
    for (let i = 0; i < visibleData.length; i++) {
      if (visibleData[i].macd !== undefined && visibleData[i].macd !== null) {
        const x = indexToX(i + startIndex) + candleWidth / 2
        const y = macdToY(visibleData[i].macd!)
        if (!macdStarted) {
          ctx.moveTo(x, y)
          macdStarted = true
        } else {
          ctx.lineTo(x, y)
        }
      }
    }
    ctx.stroke()

    // Draw Signal line (TradingView style)
    ctx.strokeStyle = '#FF6D00' // Orange
    ctx.lineWidth = 1.8
    ctx.beginPath()
    let signalStarted = false
    for (let i = 0; i < visibleData.length; i++) {
      if (visibleData[i].macd_signal !== undefined && visibleData[i].macd_signal !== null) {
        const x = indexToX(i + startIndex) + candleWidth / 2
        const y = macdToY(visibleData[i].macd_signal!)
        if (!signalStarted) {
          ctx.moveTo(x, y)
          signalStarted = true
        } else {
          ctx.lineTo(x, y)
        }
      }
    }
    ctx.stroke()
  }

  /**
   * Draw crosshair and tooltip
   */
  const drawCrosshair = (
    ctx: CanvasRenderingContext2D,
    candle: ChartData | undefined,
    mousePos: { x: number; y: number },
    marginLeft: number,
    marginRight: number,
    chartWidth: number,
    height: number
  ) => {
    if (!candle) return

    // Crosshair lines
    ctx.strokeStyle = '#6b7280'
    ctx.lineWidth = 1
    ctx.setLineDash([4, 4])

    // Vertical line
    ctx.beginPath()
    ctx.moveTo(mousePos.x, 0)
    ctx.lineTo(mousePos.x, height)
    ctx.stroke()

    ctx.setLineDash([])

    // Tooltip box
    const tooltipX = 10
    const tooltipY = 10
    const tooltipWidth = 220
    const tooltipHeight = 160

    // Background
    ctx.fillStyle = 'rgba(10, 14, 20, 0.95)'
    ctx.strokeStyle = '#374151'
    ctx.lineWidth = 1
    ctx.fillRect(tooltipX, tooltipY, tooltipWidth, tooltipHeight)
    ctx.strokeRect(tooltipX, tooltipY, tooltipWidth, tooltipHeight)

    // Content
    ctx.font = '10px system-ui'
    ctx.textAlign = 'left'
    let lineY = tooltipY + 15

    // Time
    const date = new Date(candle.time)
    ctx.fillStyle = '#9ca3af'
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
    lineY += 16

    // OHLC
    const ohlc = [
      { label: 'O:', value: candle.open, color: '#9ca3af' },
      { label: 'H:', value: candle.high, color: '#10b981' },
      { label: 'L:', value: candle.low, color: '#ef4444' },
      { label: 'C:', value: candle.close, color: candle.close >= candle.open ? '#10b981' : '#ef4444' }
    ]

    ohlc.forEach(({ label, value, color }) => {
      ctx.fillStyle = '#9ca3af'
      ctx.fillText(label, tooltipX + 10, lineY)
      ctx.fillStyle = color
      ctx.fillText(value.toFixed(value > 100 ? 2 : 4), tooltipX + 30, lineY)
      lineY += 14
    })

    lineY += 4

    // Volume
    ctx.fillStyle = '#9ca3af'
    ctx.fillText('Vol:', tooltipX + 10, lineY)
    ctx.fillStyle = '#ffffff'
    ctx.fillText(candle.volume.toFixed(2), tooltipX + 40, lineY)
    lineY += 16

    // Indicators
    if (candle.rsi !== undefined && candle.rsi !== null) {
      ctx.fillStyle = '#9ca3af'
      ctx.fillText('RSI:', tooltipX + 10, lineY)
      ctx.fillStyle = '#8b5cf6'
      ctx.fillText(candle.rsi.toFixed(2), tooltipX + 40, lineY)
      lineY += 14
    }

    if (candle.macd !== undefined && candle.macd !== null) {
      ctx.fillStyle = '#9ca3af'
      ctx.fillText('MACD:', tooltipX + 10, lineY)
      ctx.fillStyle = '#3b82f6'
      ctx.fillText(candle.macd.toFixed(2), tooltipX + 50, lineY)
      lineY += 14
    }

    if (candle.macd_signal !== undefined && candle.macd_signal !== null) {
      ctx.fillStyle = '#9ca3af'
      ctx.fillText('Signal:', tooltipX + 10, lineY)
      ctx.fillStyle = '#f59e0b'
      ctx.fillText(candle.macd_signal.toFixed(2), tooltipX + 50, lineY)
    }
  }

  // === Event handlers ===
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

    // Calculate hovered candle (use same adaptive logic as drawChart)
    const marginLeft = 60
    const chartWidth = rect.width - 60 - 80
    
    let baseCandles: number
    if (data.length >= 800) {
      baseCandles = Math.min(200, Math.floor(data.length * 0.18))
    } else if (data.length >= 500) {
      baseCandles = Math.floor(data.length * 0.28)
    } else if (data.length >= 200) {
      baseCandles = Math.floor(data.length * 0.45)
    } else {
      baseCandles = Math.floor(data.length * 0.75)
    }
    
    const candlesPerView = Math.max(50, Math.min(data.length, Math.floor(baseCandles / zoom)))
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

    // Pan
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
    const zoomSpeed = 0.1
    const newZoom = e.deltaY < 0 ? zoom * (1 + zoomSpeed) : zoom * (1 - zoomSpeed)
    setZoom(Math.max(0.5, Math.min(5, newZoom)))
  }

  // Zoom controls
  const zoomIn = () => setZoom(Math.min(5, zoom * 1.2))
  const zoomOut = () => setZoom(Math.max(0.5, zoom / 1.2))
  const resetZoom = () => {
    setZoom(1)
    setOffset(0)
  }

  return (
    <div ref={containerRef} className="relative w-full h-full min-h-[400px]">
      <canvas
        ref={canvasRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
        onWheel={handleWheel}
        className="w-full h-full cursor-crosshair"
      />
      
      {/* Zoom controls */}
      <div className="absolute bottom-2 right-2 flex gap-1 bg-slate-900/90 border border-slate-700 rounded p-1">
        <button
          onClick={zoomIn}
          className="w-6 h-6 flex items-center justify-center text-slate-300 hover:text-white hover:bg-slate-800 rounded text-sm font-bold"
          title="Zoom In"
        >
          +
        </button>
        <button
          onClick={zoomOut}
          className="w-6 h-6 flex items-center justify-center text-slate-300 hover:text-white hover:bg-slate-800 rounded text-sm font-bold"
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

