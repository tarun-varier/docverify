import React from 'react';

interface CircularProgressProps {
  score: number;
  size?: number;
  strokeWidth?: number;
  riskLevel: string;
}

export const CircularProgress: React.FC<CircularProgressProps> = ({
  score,
  size = 200,
  strokeWidth = 14,
  riskLevel,
}) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  // Determine color based on score
  const getColor = (s: number) => {
    if (s === 0) return '#10b981'; // Green (Safe)
    if (s <= 20) return '#34d399'; // Emerald (Low Risk)
    if (s <= 55) return '#f59e0b'; // Amber (Suspicious)
    return '#ef4444'; // Red (Dangerous)
  };

  const color = getColor(score);

  return (
    <div className="flex flex-col items-center justify-center relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="transform -rotate-90">
        {/* Track Circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="transparent"
          stroke="rgba(255, 255, 255, 0.05)"
          strokeWidth={strokeWidth}
        />
        {/* Animated Progress Circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="transparent"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          style={{
            transition: 'stroke-dashoffset 0.8s ease-in-out, stroke 0.8s ease',
          }}
        />
      </svg>
      {/* Center Label */}
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        <span 
          className="text-4xl font-extrabold tracking-tight" 
          style={{ color, textShadow: `0 0 15px ${color}33` }}
        >
          {score}%
        </span>
        <span className="text-xs font-semibold uppercase tracking-widest text-slate-400 mt-1">
          {riskLevel}
        </span>
      </div>
    </div>
  );
};

export default CircularProgress;
