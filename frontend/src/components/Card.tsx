import { clsx } from "clsx";
import type { ReactNode } from "react";

export function Card({
  children,
  className,
  title,
  subtitle,
  action,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div
      className={clsx(
        "bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-5",
        className
      )}
    >
      {(title || action) && (
        <div className="flex items-center justify-between mb-4">
          <div>
            {title && <h3 className="text-sm font-semibold text-[var(--color-text)]">{title}</h3>}
            {subtitle && (
              <p className="text-xs text-[var(--color-text-muted)] mt-0.5">{subtitle}</p>
            )}
          </div>
          {action}
        </div>
      )}
      {children}
    </div>
  );
}

export function StatCard({
  label,
  value,
  icon,
  trend,
  color = "text-[var(--color-text)]",
}: {
  label: string;
  value: string | number;
  icon: string;
  trend?: string;
  color?: string;
}) {
  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-[var(--color-text-muted)] mb-1">{label}</p>
          <p className={clsx("text-2xl font-bold tabular-nums", color)}>{value}</p>
          {trend && <p className="text-xs text-[var(--color-text-muted)] mt-1">{trend}</p>}
        </div>
        <span className="text-2xl">{icon}</span>
      </div>
    </Card>
  );
}
