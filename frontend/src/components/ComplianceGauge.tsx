import { scoreToStatus } from "./StatusBadge";

const statusColors = {
  pass: "#22c55e",
  warn: "#eab308",
  fail: "#ef4444",
  healthy: "#22c55e",
  warning: "#eab308",
  critical: "#ef4444",
};

export function ComplianceGauge({ score, size = 120 }: { score: number; size?: number }) {
  const status = scoreToStatus(score);
  const color = statusColors[status];
  const radius = (size - 16) / 2;
  const circumference = Math.PI * radius; // half circle
  const progress = (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size / 2 + 16} viewBox={`0 0 ${size} ${size / 2 + 16}`}>
        {/* Background arc */}
        <path
          d={`M 8 ${size / 2 + 8} A ${radius} ${radius} 0 0 1 ${size - 8} ${size / 2 + 8}`}
          fill="none"
          stroke="var(--color-surface-2)"
          strokeWidth="8"
          strokeLinecap="round"
        />
        {/* Progress arc */}
        <path
          d={`M 8 ${size / 2 + 8} A ${radius} ${radius} 0 0 1 ${size - 8} ${size / 2 + 8}`}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={`${progress} ${circumference}`}
          className="transition-all duration-700 ease-out"
        />
        <text
          x={size / 2}
          y={size / 2}
          textAnchor="middle"
          fill={color}
          fontSize={size / 4}
          fontWeight="bold"
        >
          {score}%
        </text>
      </svg>
    </div>
  );
}
