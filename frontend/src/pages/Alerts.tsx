import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Card, StatCard } from "../components/Card";
import { Loading, ErrorDisplay, EmptyState } from "../components/Loading";

export function Alerts() {
  const [severityFilter, setSeverityFilter] = useState<string>("");
  const [regionFilter, setRegionFilter] = useState<string>("");

  const { data, isLoading, error } = useQuery({
    queryKey: ["alerts", severityFilter, regionFilter],
    queryFn: () =>
      api.getAlerts({
        severity: severityFilter || undefined,
        region: regionFilter || undefined,
      }),
    refetchInterval: 15_000,
  });

  const { data: dashboard } = useQuery({
    queryKey: ["dashboard"],
    queryFn: api.getDashboard,
  });

  const regions = dashboard?.regions.map((r) => r.name) ?? [];

  if (isLoading) return <Loading />;
  if (error) return <ErrorDisplay message={(error as Error).message} />;
  if (!data) return <EmptyState message="데이터 없음" />;

  const { alerts, summary } = data;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold">알림 센터</h2>
        <p className="text-sm text-[var(--color-text-muted)] mt-1">
          이상치 탐지 및 임계값 기반 알림
        </p>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard
          label="전체 알림"
          value={summary.total}
          icon="🔔"
          color={summary.total > 0 ? "text-yellow-400" : "text-green-400"}
        />
        <StatCard
          label="Critical"
          value={summary.critical}
          icon="🚨"
          color={summary.critical > 0 ? "text-red-400" : "text-green-400"}
        />
        <StatCard
          label="Warning"
          value={summary.warning}
          icon="⚠️"
          color={summary.warning > 0 ? "text-yellow-400" : "text-green-400"}
        />
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="bg-[var(--color-surface-2)] text-sm rounded-lg px-3 py-2 border border-[var(--color-border)]"
        >
          <option value="">모든 심각도</option>
          <option value="critical">Critical</option>
          <option value="warning">Warning</option>
        </select>
        <select
          value={regionFilter}
          onChange={(e) => setRegionFilter(e.target.value)}
          className="bg-[var(--color-surface-2)] text-sm rounded-lg px-3 py-2 border border-[var(--color-border)]"
        >
          <option value="">모든 리전</option>
          {regions.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
      </div>

      {/* Alert list */}
      {alerts.length === 0 ? (
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-6 text-center">
          <span className="text-3xl">✅</span>
          <p className="mt-2 font-medium">알림 없음</p>
          <p className="text-sm text-[var(--color-text-muted)]">
            모든 시스템이 정상 범위 내에서 운영되고 있습니다
          </p>
        </div>
      ) : (
        <Card title="활성 알림">
          <div className="space-y-3">
            {alerts.map((alert, i) => (
              <div
                key={i}
                className={`rounded-lg p-4 border ${
                  alert.severity === "critical"
                    ? "bg-red-500/5 border-red-500/30"
                    : "bg-yellow-500/5 border-yellow-500/30"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span>
                      {alert.severity === "critical" ? "🚨" : "⚠️"}
                    </span>
                    <div>
                      <p className="text-sm font-medium">{alert.message}</p>
                      <div className="flex items-center gap-2 mt-1 text-xs text-[var(--color-text-muted)]">
                        {alert.server_id && (
                          <span className="bg-[var(--color-surface-2)] px-2 py-0.5 rounded">
                            {alert.hostname ?? alert.server_id}
                          </span>
                        )}
                        {alert.region && (
                          <span className="bg-[var(--color-surface-2)] px-2 py-0.5 rounded">
                            {alert.region}
                          </span>
                        )}
                        {alert.role && (
                          <span className="bg-[var(--color-surface-2)] px-2 py-0.5 rounded capitalize">
                            {alert.role}
                          </span>
                        )}
                        <span className="bg-[var(--color-surface-2)] px-2 py-0.5 rounded">
                          {alert.type.replace(/_/g, " ")}
                        </span>
                      </div>
                    </div>
                  </div>
                  <span
                    className={`text-xs px-2 py-1 rounded whitespace-nowrap ${
                      alert.severity === "critical"
                        ? "bg-red-500/20 text-red-400"
                        : "bg-yellow-500/20 text-yellow-400"
                    }`}
                  >
                    {alert.severity}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
