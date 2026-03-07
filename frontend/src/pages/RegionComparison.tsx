import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { RegionComparisonEntry } from "../api/client";
import { Card } from "../components/Card";
import { Loading, ErrorDisplay, EmptyState } from "../components/Loading";
import { ScoreDisplay, StatusBadge } from "../components/StatusBadge";

export function RegionComparison() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["region-comparison"],
    queryFn: api.getRegionComparison,
    refetchInterval: 30_000,
  });

  if (isLoading) return <Loading />;
  if (error) return <ErrorDisplay message={(error as Error).message} />;
  if (!data || data.regions.length === 0) return <EmptyState message="리전 데이터 없음" />;

  const { regions, best_region, worst_region, cross_region_drift } = data;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold">리전 비교</h2>
        <p className="text-sm text-[var(--color-text-muted)] mt-1">
          멀티 리전 compliance 비교 및 이상치 탐지
        </p>
      </div>

      {/* Best / Worst region badges */}
      {best_region && worst_region && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4 flex items-center gap-3">
            <span className="text-2xl">🏆</span>
            <div>
              <p className="text-xs text-green-400 font-medium">Best Region</p>
              <p className="text-lg font-bold capitalize">{best_region.name}</p>
              <p className="text-sm text-green-300">{best_region.score}%</p>
            </div>
          </div>
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex items-center gap-3">
            <span className="text-2xl">⚠️</span>
            <div>
              <p className="text-xs text-red-400 font-medium">Needs Attention</p>
              <p className="text-lg font-bold capitalize">{worst_region.name}</p>
              <p className="text-sm text-red-300">{worst_region.score}%</p>
            </div>
          </div>
        </div>
      )}

      {/* Region comparison cards */}
      <Card title="리전별 상세 비교">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {regions.map((r) => (
            <RegionCard key={r.region} region={r} />
          ))}
        </div>
      </Card>

      {/* Cross-region drift */}
      {cross_region_drift.length > 0 && (
        <Card title="리전 간 Drift 감지">
          <div className="space-y-3">
            {cross_region_drift.map((d) => (
              <div
                key={d.role}
                className="bg-[var(--color-surface-2)] rounded-lg p-4"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-sm capitalize">{d.role}</span>
                  <span
                    className={`text-xs font-mono px-2 py-1 rounded ${
                      d.drift_percentage >= 20
                        ? "bg-red-500/20 text-red-400"
                        : "bg-yellow-500/20 text-yellow-400"
                    }`}
                  >
                    Drift: {d.drift_percentage}%
                  </span>
                </div>
                <div className="flex items-center gap-4 text-xs text-[var(--color-text-muted)]">
                  <span>
                    🟢 {d.best_region}: {d.best_score}%
                  </span>
                  <span>→</span>
                  <span>
                    🔴 {d.worst_region}: {d.worst_score}%
                  </span>
                </div>
                {Object.keys(d.all_regions).length > 2 && (
                  <div className="mt-2 flex gap-2 flex-wrap">
                    {Object.entries(d.all_regions).map(([region, score]) => (
                      <span
                        key={region}
                        className="text-xs bg-[var(--color-surface)] px-2 py-1 rounded"
                      >
                        {region}: {score}%
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function RegionCard({ region }: { region: RegionComparisonEntry }) {
  const status =
    region.average_compliance >= 80
      ? "healthy"
      : region.average_compliance >= 60
        ? "warning"
        : ("critical" as const);

  return (
    <div className="bg-[var(--color-surface-2)] rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="font-medium capitalize">{region.region}</span>
        <StatusBadge status={status} />
      </div>
      <div className="grid grid-cols-2 gap-3 text-sm mb-3">
        <div>
          <p className="text-xs text-[var(--color-text-muted)]">평균 점수</p>
          <ScoreDisplay score={region.average_compliance} />
        </div>
        <div>
          <p className="text-xs text-[var(--color-text-muted)]">서버 수</p>
          <p className="font-medium">{region.server_count}</p>
        </div>
        <div>
          <p className="text-xs text-[var(--color-text-muted)]">최저/최고</p>
          <p className="font-mono text-xs">
            {region.min_compliance}% — {region.max_compliance}%
          </p>
        </div>
        <div>
          <p className="text-xs text-[var(--color-text-muted)]">Issues</p>
          <p className="font-mono text-xs">
            <span className="text-red-400">{region.critical_issues}C</span>
            {" / "}
            <span className="text-yellow-400">{region.warning_issues}W</span>
          </p>
        </div>
      </div>
      {region.roles.length > 0 && (
        <div className="border-t border-[var(--color-border)] pt-2 mt-2">
          <p className="text-xs text-[var(--color-text-muted)] mb-1">역할별</p>
          <div className="flex gap-2 flex-wrap">
            {region.roles.map((r) => (
              <span
                key={r.role}
                className="text-xs bg-[var(--color-surface)] px-2 py-1 rounded"
              >
                {r.role}: {r.average_score}% ({r.servers})
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
