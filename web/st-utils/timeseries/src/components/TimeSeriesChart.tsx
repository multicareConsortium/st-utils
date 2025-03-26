import React from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ChartOptions
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { format } from 'date-fns';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

interface TimeSeriesData {
  date: Date;
  value: number;
  trend: number;
  forecast: number;
  volatility: number;
  volume: number;
}

interface TimeSeriesChartProps {
  data: TimeSeriesData[];
  title: string;
  showVolatility?: boolean;
}

export const TimeSeriesChart: React.FC<TimeSeriesChartProps> = ({ 
  data, 
  title,
  showVolatility = false 
}) => {
  const options: ChartOptions<'line'> = {
    responsive: true,
    interaction: {
      mode: 'index' as const,
      intersect: false,
    },
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: true,
        text: title,
        font: {
          size: 16,
          weight: 'bold'
        }
      },
      tooltip: {
        callbacks: {
          label: (context) => {
            const value = context.raw as number;
            return `${context.dataset.label}: ${value.toFixed(2)}`;
          }
        }
      }
    },
    scales: {
      x: {
        ticks: {
          maxRotation: 45,
          minRotation: 45
        },
        grid: {
          display: false
        }
      },
      y: {
        grid: {
          color: 'rgba(0, 0, 0, 0.1)'
        }
      }
    }
  };

  const datasets = [
    {
      label: 'Actual',
      data: data.map(d => d.value),
      borderColor: 'rgb(75, 192, 192)',
      backgroundColor: 'rgba(75, 192, 192, 0.5)',
      tension: 0.4
    },
    {
      label: 'Trend',
      data: data.map(d => d.trend),
      borderColor: 'rgb(255, 99, 132)',
      backgroundColor: 'rgba(255, 99, 132, 0.5)',
      tension: 0.4
    },
    {
      label: 'Forecast',
      data: data.map(d => d.forecast),
      borderColor: 'rgb(53, 162, 235)',
      backgroundColor: 'rgba(53, 162, 235, 0.5)',
      borderDash: [5, 5],
      tension: 0.4
    }
  ];

  if (showVolatility) {
    datasets.push({
      label: 'Volatility',
      data: data.map(d => d.volatility),
      borderColor: 'rgb(153, 102, 255)',
      backgroundColor: 'rgba(153, 102, 255, 0.5)',
      tension: 0.4
    });
  }

  const chartData = {
    labels: data.map(d => format(d.date, 'MMM d, yyyy')),
    datasets
  };

  return <Line options={options} data={chartData} />;
};