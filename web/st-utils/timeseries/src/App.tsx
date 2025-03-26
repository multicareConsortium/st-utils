import React, { useState } from 'react';
import { TimeSeriesChart } from './components/TimeSeriesChart';
import { StatCard } from './components/StatCard';
import { generateTimeSeriesData } from './utils/generateData';
import { 
  LineChart, 
  TrendingUp, 
  Activity, 
  BarChart3, 
  Calendar,
  RefreshCw
} from 'lucide-react';

function App() {
  const [timeRange, setTimeRange] = useState<30 | 90>(30);
  const data = generateTimeSeriesData(timeRange);
  
  // Calculate summary statistics
  const latestValue = data[data.length - 1].value;
  const previousValue = data[0].value;
  const valueTrend = ((latestValue - previousValue) / previousValue) * 100;
  
  const avgVolatility = data.reduce((sum, d) => sum + d.volatility, 0) / data.length;
  const avgVolume = Math.floor(data.reduce((sum, d) => sum + d.volume, 0) / data.length);
  
  return (
    <div className="min-h-screen bg-gray-100">
      <div className="p-8">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-3">
              <LineChart className="w-8 h-8 text-blue-600" />
              <h1 className="text-3xl font-bold text-gray-800">Analytics Dashboard</h1>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setTimeRange(30)}
                className={`px-4 py-2 rounded-lg ${
                  timeRange === 30 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-white text-gray-600 hover:bg-gray-50'
                }`}
              >
                30 Days
              </button>
              <button
                onClick={() => setTimeRange(90)}
                className={`px-4 py-2 rounded-lg ${
                  timeRange === 90 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-white text-gray-600 hover:bg-gray-50'
                }`}
              >
                90 Days
              </button>
            </div>
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <StatCard
              title="Current Value"
              value={latestValue.toFixed(2)}
              trend={valueTrend}
              icon={TrendingUp}
            />
            <StatCard
              title="Average Volatility"
              value={avgVolatility.toFixed(2)}
              trend={-2.5}
              icon={Activity}
            />
            <StatCard
              title="Average Volume"
              value={avgVolume.toLocaleString()}
              trend={5.8}
              icon={BarChart3}
            />
            <StatCard
              title="Data Points"
              value={data.length}
              trend={0}
              icon={Calendar}
            />
          </div>
          
          {/* Charts */}
          <div className="grid gap-8">
            <div className="bg-white p-6 rounded-lg shadow-lg">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-gray-800">Time Series Analysis</h2>
                <button 
                  onClick={() => setTimeRange(timeRange)}
                  className="p-2 hover:bg-gray-100 rounded-full transition-colors"
                >
                  <RefreshCw className="w-5 h-5 text-gray-600" />
                </button>
              </div>
              <TimeSeriesChart 
                data={data} 
                title={`${timeRange} Day Analysis`}
              />
            </div>
            
            <div className="bg-white p-6 rounded-lg shadow-lg">
              <h2 className="text-xl font-semibold text-gray-800 mb-4">Volatility Analysis</h2>
              <TimeSeriesChart 
                data={data} 
                title="Market Volatility Trends"
                showVolatility={true}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;