import React, { useMemo } from 'react';
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts';

// Define a stable color map for sentiments. This will be our single source of truth for colors.
const SENTIMENT_COLORS = {
  positive: '#10b981', // green
  negative: '#ef4444', // red
  neutral: '#f59e0b',  // yellow
  unknown: '#64748b',  // slate
};

const normalizeSentiment = (value) => {
  const label = String(value || '').trim().toLowerCase();
  if (['positive', 'negative', 'neutral', 'unknown'].includes(label)) return label;
  if (label.includes('pos')) return 'positive';
  if (label.includes('neg')) return 'negative';
  if (label.includes('neu')) return 'neutral';
  return 'unknown';
};


export function Charts({ comments }) {
  // Pie chart data calculation remains the same.
  const pieData = useMemo(() => {
    const counts = comments.reduce((acc, c) => {
      const sentiment = normalizeSentiment(c.sentiment);
      acc[sentiment] = (acc[sentiment] || 0) + 1;
      return acc;
    }, {});

    return Object.keys(counts)
      .filter(key => counts[key] > 0)
      .map(key => ({
        name: key.charAt(0).toUpperCase() + key.slice(1),
        value: counts[key],
      }));
  }, [comments]);

  // FIX: The bar chart data now needs to include the sentiment label for correct coloring.
  const barData = useMemo(() => {
    return comments.map((c, idx) => ({
      index: idx + 1,
      score: c.sentiment_score,
      sentiment: normalizeSentiment(c.sentiment), // Pass the sentiment label to each bar
    }));
  }, [comments]);


  return (
    <div className="chart-container-wrapper">
      {/* --- PIE CHART SECTION --- */}
      <div>
        <h4>Sentiment Distribution</h4>
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie
              data={pieData}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              outerRadius={110}
              label={({ name, percent }) => `${(percent * 100).toFixed(0)}%`}
              labelLine={false}
            >
              {pieData.map((entry) => (
                <Cell key={`cell-${entry.name}`} fill={SENTIMENT_COLORS[entry.name.toLowerCase()]} />
              ))}
            </Pie>
            <Tooltip formatter={(value, name) => [`${value} comments`, name]} />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* --- BAR CHART SECTION (CORRECTED LOGIC) --- */}
      <div>
        <h4>Sentiment Score (by comment)</h4>
        <ResponsiveContainer width="100%" height={300}>
            <BarChart data={barData} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="index" tick={{fontSize: 12}} />
                <YAxis domain={[0, 1]} tick={{fontSize: 12}} />
                <Tooltip cursor={{fill: 'rgba(230, 230, 230, 0.5)'}} />
                
                {/* FIX: The <Bar> component now uses the 'sentiment' property from barData to set the color of each bar. */}
                <Bar dataKey="score">
                    {barData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={SENTIMENT_COLORS[entry.sentiment]} />
                    ))}
                </Bar>
            </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default Charts;
