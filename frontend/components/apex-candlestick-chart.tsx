'use client'

import { useEffect, useState, useMemo } from 'react'
import dynamic from 'next/dynamic'
import { ChartData } from '@/lib/api'

// Dynamic import untuk ApexCharts (client-side only)
const Chart = dynamic(() => import('react-apexcharts'), { ssr: false })

interface ApexCandlestickChartProps {
  data: ChartData[]
  height?: string | number
  showRSI?: boolean
  showMACD?: boolean
  showVolume?: boolean
  showMA?: boolean
}

/**
 * Professional Candlestick Chart using ApexCharts
 * Based on: https://apexcharts.com/docs/chart-types/candlestick/
 * 
 * Features:
 * - Candlestick with OHLC data
 * - Moving Averages (MA20, MA50)
 * - RSI Indicator panel
 * - MACD Indicator panel
 * - Volume bars
 * - Professional TradingView-like styling
 */
export default function ApexCandlestickChart({
  data,
  height = '100%',
  showRSI = true,
  showMACD = true,
  showVolume = true,
  showMA = true,
}: ApexCandlestickChartProps) {
  const [chartReady, setChartReady] = useState(false)

  useEffect(() => {
    setChartReady(true)
  }, [])

  // Prepare and validate data - OPTIMIZED: Limit data size for performance
  const preparedData = useMemo(() => {
    if (!data || data.length === 0) return null

    // OPTIMIZATION: Limit to last 500 candles max for better performance
    const limitedData = data.slice(-500)

    // Filter valid candlestick data (simplified validation)
    const validData = limitedData.filter((d) => {
      return (
        d &&
        d.time &&
        typeof d.open === 'number' &&
        typeof d.high === 'number' &&
        typeof d.low === 'number' &&
        typeof d.close === 'number' &&
        d.high >= d.low
      )
    })

    if (validData.length === 0) return null

    return validData
  }, [data])

  // Prepare candlestick data in ApexCharts format: [timestamp, O, H, L, C]
  const candlestickData = useMemo(() => {
    if (!preparedData || preparedData.length === 0) return []
    
    return preparedData
      .map((d) => {
        const timestamp = typeof d.time === 'number' ? d.time : new Date(d.time).getTime()
        // Ensure all values are numbers and valid
        const open = Number(d.open) || 0
        const high = Number(d.high) || 0
        const low = Number(d.low) || 0
        const close = Number(d.close) || 0
        return [timestamp, open, high, low, close]
      })
      .filter((d) => d[0] && d[1] && d[2] && d[3] && d[4]) // Filter out invalid entries
  }, [preparedData])

  // Prepare series for main chart - MUST USE useMemo to avoid issues
  const mainSeries = useMemo(() => {
    const series: any[] = [
      {
        name: 'Candlestick',
        data: Array.isArray(candlestickData) ? candlestickData : [],
      },
    ]

    if (showMA && preparedData && preparedData.length > 0) {
      const ma20Data: any[] = []
      const ma50Data: any[] = []

      preparedData.forEach((d) => {
        const timestamp = typeof d.time === 'number' ? d.time : new Date(d.time).getTime()
        if (d.ma20 !== undefined && d.ma20 !== null && !isNaN(d.ma20)) {
          ma20Data.push([timestamp, d.ma20])
        }
        if (d.ma50 !== undefined && d.ma50 !== null && !isNaN(d.ma50)) {
          ma50Data.push([timestamp, d.ma50])
        }
      })

      if (ma20Data.length > 0) {
        series.push({
          name: 'MA20',
          type: 'line',
          data: ma20Data,
        })
      }
      if (ma50Data.length > 0) {
        series.push({
          name: 'MA50',
          type: 'line',
          data: ma50Data,
        })
      }
    }

    return series
  }, [candlestickData, showMA, preparedData])

  // Calculate height percentages
  const hasIndicators = useMemo(() => {
    if (!preparedData || preparedData.length === 0) return false
    return (
      (showRSI && preparedData.some((d) => d.rsi)) ||
      (showMACD && preparedData.some((d) => d.macd)) ||
      (showVolume && preparedData.some((d) => d.volume))
    )
  }, [preparedData, showRSI, showMACD, showVolume])
  
  const mainHeight = hasIndicators ? '65%' : '100%'

  // Main chart options - MUST USE useMemo since it depends on mainSeries
  const mainChartOptions: any = useMemo(() => ({
    chart: {
      type: 'candlestick',
      height: typeof height === 'string' ? (height.includes('%') ? mainHeight : height) : mainHeight,
      group: 'candlestick-chart',
      toolbar: {
        show: true,
        tools: {
          download: false, // Disabled for performance
          selection: true,
          zoom: true,
          zoomin: true,
          zoomout: true,
          pan: true,
          reset: true,
        },
        autoSelected: 'zoom',
      },
      zoom: {
        enabled: true,
        type: 'x',
        autoScaleYaxis: true,
      },
      selection: {
        enabled: true,
        fill: {
          color: '#90cdf4',
          opacity: 0.1,
        },
        stroke: {
          width: 1,
          dashArray: 3,
          color: '#90cdf4',
        },
      },
      animations: {
        enabled: false, // Disabled for better performance
        easing: 'easeinout',
        speed: 800,
      },
      background: 'transparent',
      foreColor: '#848e9c',
    },
    plotOptions: {
      candlestick: {
        colors: {
          upward: '#26a69a', // Green for bullish
          downward: '#ef5350', // Red for bearish
        },
        wick: {
          useFillColor: true, // Use same color as candle body for wick
        },
      },
    },
    stroke: {
      width: showMA && mainSeries.length > 1 ? [0, 2, 2] : [0],
      curve: 'smooth',
    },
    colors: ['#26a69a', '#3C90EB', '#F7B731'], // Candlestick default, MA20, MA50
    xaxis: {
      type: 'datetime',
      labels: {
        style: {
          colors: '#848e9c',
          fontSize: '11px',
        },
        datetimeFormatter: {
          year: 'yyyy',
          month: "MMM 'yy",
          day: 'dd MMM',
          hour: 'HH:mm',
        },
      },
      axisBorder: {
        show: true,
        color: '#1e2329',
      },
      axisTicks: {
        show: true,
        color: '#1e2329',
      },
    },
    yaxis: {
      labels: {
        style: {
          colors: '#848e9c',
          fontSize: '11px',
        },
        formatter: (val: number) => {
          if (val === null || val === undefined || isNaN(val)) return ''
          return val.toFixed(val > 100 ? 2 : 4)
        },
      },
      tooltip: {
        enabled: true,
      },
    },
    grid: {
      borderColor: '#1e2329',
      strokeDashArray: 0,
      xaxis: {
        lines: {
          show: true,
        },
      },
      yaxis: {
        lines: {
          show: true,
        },
      },
      padding: {
        top: 0,
        right: 10,
        bottom: 0,
        left: 10,
      },
    },
    tooltip: {
      enabled: true,
      shared: false,
      theme: 'dark',
      style: {
        fontSize: '12px',
      },
      // Simplified tooltip for better performance
      x: {
        formatter: (val: number) => {
          return new Date(val).toLocaleString()
        },
      },
      y: {
        formatter: (val: number) => {
          return val.toFixed(val > 100 ? 2 : 4)
        },
      },
    },
    legend: {
      show: showMA && mainSeries.length > 1,
      position: 'top',
      horizontalAlign: 'right',
      fontSize: '11px',
      labels: {
        colors: '#848e9c',
      },
      markers: {
        width: 8,
        height: 8,
        radius: 2,
      },
    },
    theme: {
      mode: 'dark',
      palette: 'palette1',
    },
    dataLabels: {
      enabled: false,
    },
  }), [mainSeries, mainHeight, showMA])

  // Prepare RSI data - MUST BE CALLED EVERY RENDER (Rules of Hooks)
  const rsiData = useMemo(() => {
    if (!showRSI || !preparedData || preparedData.length === 0) return []
    return preparedData
      .map((d) => {
        const timestamp = typeof d.time === 'number' ? d.time : new Date(d.time).getTime()
        if (d.rsi !== undefined && d.rsi !== null && !isNaN(d.rsi)) {
          return [timestamp, d.rsi]
        }
        return null
      })
      .filter((d): d is [number, number] => d !== null)
  }, [preparedData, showRSI])

  // Prepare MACD data - MUST BE CALLED EVERY RENDER (Rules of Hooks)
  const macdData = useMemo(() => {
    if (!showMACD || !preparedData || preparedData.length === 0) return { macd: [], signal: [] }
    const macd: any[] = []
    const signal: any[] = []

    preparedData.forEach((d) => {
      const timestamp = typeof d.time === 'number' ? d.time : new Date(d.time).getTime()
      if (d.macd !== undefined && d.macd !== null && !isNaN(d.macd)) {
        macd.push([timestamp, d.macd])
      }
      if (d.macd_signal !== undefined && d.macd_signal !== null && !isNaN(d.macd_signal)) {
        signal.push([timestamp, d.macd_signal])
      }
    })

    return { macd, signal }
  }, [preparedData, showMACD])

  // Prepare Volume data - MUST BE CALLED EVERY RENDER (Rules of Hooks)
  const volumeData = useMemo(() => {
    if (!showVolume || !preparedData || preparedData.length === 0) return { data: [], colors: [] }
    const data: any[] = []
    const colors: string[] = []

    preparedData.forEach((d) => {
      const timestamp = typeof d.time === 'number' ? d.time : new Date(d.time).getTime()
      if (d.volume !== undefined && d.volume !== null && !isNaN(d.volume)) {
        const volume = Number(d.volume) || 0
        const isUp = (d.close || 0) >= (d.open || 0)
        data.push([timestamp, volume])
        colors.push(isUp ? '#26a69a' : '#ef5350')
      }
    })

    return { data, colors }
  }, [preparedData, showVolume])

  const hasRSI = showRSI && rsiData.length > 0
  const hasMACD = showMACD && macdData.macd.length > 0
  const hasVol = showVolume && volumeData.data.length > 0

  // Now we can do conditional rendering instead of early returns
  if (!chartReady) {
    return (
      <div className="flex items-center justify-center h-full text-slate-400">
        <div className="text-center">
          <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mx-auto mb-2"></div>
          <p className="text-xs">Loading chart...</p>
        </div>
      </div>
    )
  }

  if (!preparedData || preparedData.length === 0 || !candlestickData || candlestickData.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-slate-400">
        <div className="text-center">
          <p className="text-xs">No valid chart data available</p>
        </div>
      </div>
    )
  }

  return (
    <div className="w-full h-full bg-slate-950 flex flex-col">
      {/* Main Candlestick Chart */}
      <div className="flex-1 min-h-0" style={{ height: mainHeight }}>
        <Chart
          options={mainChartOptions}
          series={mainSeries}
          type="candlestick"
          height="100%"
        />
      </div>

      {/* RSI Panel */}
      {hasRSI && (
        <div style={{ height: '18%' }} className="border-t border-slate-800 flex-shrink-0">
          <Chart
            options={{
              chart: {
                type: 'line',
                height: '100%',
                group: 'candlestick-chart',
                toolbar: { show: false },
                zoom: { enabled: false },
                background: 'transparent',
                foreColor: '#848e9c',
                animations: { enabled: false }, // Disable animations for performance
              },
              stroke: { width: 2, curve: 'smooth' },
              colors: ['#9c27b0'],
              xaxis: {
                type: 'datetime',
                labels: { show: false },
                axisBorder: { show: false },
                axisTicks: { show: false },
              },
              yaxis: {
                min: 0,
                max: 100,
                tickAmount: 5,
                labels: {
                  style: { colors: '#848e9c', fontSize: '10px' },
                },
              },
              grid: {
                borderColor: '#1e2329',
                xaxis: { lines: { show: false } },
                yaxis: { lines: { show: true } },
              },
              // Simplified annotations for performance
              annotations: {
                yaxis: [
                  {
                    y: 70,
                    borderColor: '#ef5350',
                    borderWidth: 1,
                    strokeDashArray: 3,
                  },
                  {
                    y: 30,
                    borderColor: '#26a69a',
                    borderWidth: 1,
                    strokeDashArray: 3,
                  },
                ],
              },
              tooltip: { enabled: true, theme: 'dark' },
              dataLabels: { enabled: false },
            }}
            series={[
              {
                name: 'RSI',
                data: Array.isArray(rsiData) && rsiData.length > 0 ? rsiData : [],
              },
            ]}
            type="line"
            height="100%"
          />
        </div>
      )}

      {/* MACD Panel */}
      {hasMACD && (
        <div style={{ height: '17%' }} className="border-t border-slate-800 flex-shrink-0">
          <Chart
            options={{
              chart: {
                type: 'line',
                height: '100%',
                group: 'candlestick-chart',
                toolbar: { show: false },
                zoom: { enabled: false },
                background: 'transparent',
                foreColor: '#848e9c',
                animations: { enabled: false }, // Disable animations for performance
              },
              stroke: { width: 2, curve: 'smooth' },
              colors: ['#26a69a', '#ef5350'],
              xaxis: {
                type: 'datetime',
                labels: { show: !hasVol, style: { colors: '#848e9c', fontSize: '10px' } },
                axisBorder: { show: false },
                axisTicks: { show: false },
              },
              yaxis: {
                labels: { style: { colors: '#848e9c', fontSize: '10px' } },
              },
              grid: {
                borderColor: '#1e2329',
                xaxis: { lines: { show: false } },
                yaxis: { lines: { show: true } },
              },
              tooltip: { enabled: true, theme: 'dark' },
              legend: {
                show: false,
              },
              dataLabels: { enabled: false },
            }}
            series={[
              {
                name: 'MACD',
                data: Array.isArray(macdData.macd) && macdData.macd.length > 0 ? macdData.macd : [],
              },
              {
                name: 'Signal',
                data: Array.isArray(macdData.signal) && macdData.signal.length > 0 ? macdData.signal : [],
              },
            ]}
            type="line"
            height="100%"
          />
        </div>
      )}

      {/* Volume Panel */}
      {hasVol && (
        <div style={{ height: '10%' }} className="border-t border-slate-800 flex-shrink-0">
          <Chart
            options={{
              chart: {
                type: 'bar',
                height: '100%',
                group: 'candlestick-chart',
                toolbar: { show: false },
                zoom: { enabled: false },
                background: 'transparent',
                foreColor: '#848e9c',
                animations: { enabled: false }, // Disable animations for performance
              },
              plotOptions: {
                bar: {
                  columnWidth: '60%',
                  distributed: true,
                },
              },
              colors: volumeData.colors.length > 0 ? volumeData.colors : ['#26a69a'],
              xaxis: {
                type: 'datetime',
                labels: { style: { colors: '#848e9c', fontSize: '10px' } },
                axisBorder: { show: false },
                axisTicks: { show: false },
              },
              yaxis: {
                labels: {
                  style: { colors: '#848e9c', fontSize: '10px' },
                  formatter: (val: number) => {
                    if (val === null || val === undefined || isNaN(val)) return ''
                    if (val >= 1e9) return (val / 1e9).toFixed(1) + 'B'
                    if (val >= 1e6) return (val / 1e6).toFixed(1) + 'M'
                    if (val >= 1e3) return (val / 1e3).toFixed(1) + 'K'
                    return val.toFixed(0)
                  },
                },
              },
              grid: {
                borderColor: '#1e2329',
                xaxis: { lines: { show: false } },
                yaxis: { lines: { show: true } },
              },
              tooltip: { enabled: true, theme: 'dark' },
              legend: {
                show: false,
              },
              dataLabels: { enabled: false },
            }}
            series={[
              {
                name: 'Volume',
                data: volumeData && volumeData.data && Array.isArray(volumeData.data) && volumeData.data.length > 0 
                  ? volumeData.data 
                  : [],
              },
            ]}
            type="bar"
            height="100%"
          />
        </div>
      )}
    </div>
  )
}
