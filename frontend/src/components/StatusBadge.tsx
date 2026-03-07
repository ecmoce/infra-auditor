import { clsx } from "clsx";

type Variant = "pass" | "warn" | "fail" | "healthy" | "warning" | "critical";

const styles: Record<Variant, string> = {
  pass: "bg-green-500/20 text-green-400 border-green-500/30",
  healthy: "bg-green-500/20 text-green-400 border-green-500/30",
  warn: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  warning: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  fail: "bg-red-500/20 text-red-400 border-red-500/30",
  critical: "bg-red-500/20 text-red-400 border-red-500/30",
};

const dots: Record<Variant, string> = {
  pass: "bg-green-400",
  healthy: "bg-green-400",
  warn: "bg-yellow-400",
  warning: "bg-yellow-400",
  fail: "bg-red-400",
  critical: "bg-red-400",
};

export function StatusBadge({ status, label }: { status: Variant; label?: string }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border",
        styles[status]
      )}
    >
      <span className={clsx("w-1.5 h-1.5 rounded-full", dots[status])} />
      {label ?? status}
    </span>
  );
}

export function scoreToStatus(score: number): Variant {
  if (score >= 80) return "pass";
  if (score >= 60) return "warn";
  return "fail";
}

export function ScoreDisplay({ score }: { score: number }) {
  const status = scoreToStatus(score);
  const colors: Record<Variant, string> = {
    pass: "text-green-400",
    healthy: "text-green-400",
    warn: "text-yellow-400",
    warning: "text-yellow-400",
    fail: "text-red-400",
    critical: "text-red-400",
  };
  return <span className={clsx("font-bold tabular-nums", colors[status])}>{score}%</span>;
}
