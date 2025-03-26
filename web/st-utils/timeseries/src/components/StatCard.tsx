import React from 'react';
import { DivideIcon as LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  trend: number;
  icon: LucideIcon;
}

export const StatCard: React.FC<StatCardProps> = ({ title, value, trend, icon: Icon }) => {
  const trendColor = trend >= 0 ? 'text-green-600' : 'text-red-600';
  const trendSign = trend >= 0 ? '+' : '';
  
  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600 mb-1">{title}</p>
          <h3 className="text-2xl font-bold text-gray-900">{value}</h3>
        </div>
        <div className="bg-blue-100 p-3 rounded-full">
          <Icon className="w-6 h-6 text-blue-600" />
        </div>
      </div>
      <div className="mt-4">
        <span className={`${trendColor} text-sm font-semibold`}>
          {trendSign}{trend}%
        </span>
        <span className="text-gray-500 text-sm ml-2">vs last period</span>
      </div>
    </div>
  );
};