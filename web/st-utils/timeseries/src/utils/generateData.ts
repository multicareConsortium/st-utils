import { addDays, subDays } from 'date-fns';

export const generateTimeSeriesData = (days: number) => {
  const endDate = new Date();
  const startDate = subDays(endDate, days);
  
  const data = [];
  let currentDate = startDate;
  
  while (currentDate <= endDate) {
    const value = Math.random() * 100;
    data.push({
      date: currentDate,
      value: value,
      trend: Math.sin(data.length / 10) * 30 + 50,
      forecast: Math.cos(data.length / 8) * 20 + 60,
      volatility: Math.abs(Math.sin(data.length / 5) * 15),
      volume: Math.floor(Math.random() * 1000) + 500
    });
    currentDate = addDays(currentDate, 1);
  }
  
  return data;
};