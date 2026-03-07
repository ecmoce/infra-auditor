import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Card, StatCard } from "../components/Card";
import { ComplianceGauge } from "../components/ComplianceGauge";
import { StatusBadge, ScoreDisplay } from "../components/StatusBadge";
import { Loading, ErrorDisplay, EmptyState } from "../components/Loading";

export function Dashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: api.getDashboard,
    refetchInterval: 30_000,
  });

  if (isLoading) return <Loading />;
  if (error) return <ErrorDisplay message={(error as Error).message} />;
  if (!data) return <EmptyState message="데이터가 없습니다" />;

  const { overall, regions, roles } = data;

  return (
    <div className="space-y-6">
      {/* Page title */}
      <div>
        <h2 className="text-xl font-bold">Mission Control</h2>
        <p className="text-sm text-[var(--color-text-muted)] mt-1">인프라 전체 현황</p>
      </div>

      {/* Alert Zone */}
      {overall.critical_issues > 0 && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-lg">🚨</span>
            <span className="text-sm font-semibold text-red-400">
              Critical Issues: {overall.critical_issues}
            </span>
          </div>
          <p className="text-xs text-red-300/80">
            {overall.critical_issues}개의 심각한 이슈가 즉각적인 조치를 필요로 합니다.
          </p>
        </div>
      )}

      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="전체 서버" value={overall.total_servers} icon="🖥️" />
        <StatCard
          label="평균 컴플라이언스"
          value={`${overall.average_compliance}%`}
          icon="📊"
          color={
            overall.average_compliance >= 80
              ? "text-green-400"
              : overall.average_compliance >= 60
                ? "text-yellow-400"
                : "text-red-400"
          }
        />
        <StatCard
          label="Critical Issues"
          value={overall.critical_issues}
          icon="💥"
          color={overall.critical_issues > 0 ? "text-red-400" : "text-green-400"}
        />
        <StatCard
          label="Warning Issues"
          value={overall.warning_issues}
          icon="⚠️"
          color={overall.warning_issues > 0 ? "text-yellow-400" : "text-green-400"}
        />
      </div>

      {/* Overall gauge + regions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title="전체 컴플라이언스">
          <div className="flex justify-center py-4">
            <ComplianceGauge score={overall.average_compliance} size={160} />
          </div>
          <p className="text-center text-xs text-[var(--color-text-muted)] mt-2">
            마지막 업데이트: {new Date(overall.last_updated).toLocaleString("ko-KR")}
          </p>
        </Card>

        <Card title="지역별 상태" className="lg:col-span-2">
          {regions.length === 0 ? (
            <EmptyState message="지역 데이터 없음" />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {regions.map((r) => (
                <Link
                  key={r.name}
                  to={`/region/${r.name}`}
                  className="block bg-[var(--color-surface-2)] rounded-lg p-4 hover:ring-1 hover:ring-[var(--color-accent)] transition-all"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-sm capitalize">{r.name}</span>
                    <StatusBadge status={r.status} />
                  </div>
                  <div className="flex items-end justify-between">
                    <ScoreDisplay score={r.compliance} />
                    <span className="text-xs text-[var(--color-text-muted)]">
                      {r.servers} servers
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Roles breakdown */}
      <Card title="역할별 현황">
        {roles.length === 0 ? (
          <EmptyState message="역할 데이터 없음" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
                  <th className="pb-3 font-medium">역할</th>
                  <th className="pb-3 font-medium">서버 수</th>
                  <th className="pb-3 font-medium">컴플라이언스</th>
                  <th className="pb-3 font-medium">상태</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)]">
                {roles.map((role) => (
                  <tr key={role.name} className="hover:bg-[var(--color-surface-2)] transition-colors">
                    <td className="py-3 font-medium capitalize">{role.name}</td>
                    <td className="py-3 tabular-nums">{role.servers}</td>
                    <td className="py-3">
                      <ScoreDisplay score={role.compliance} />
                    </td>
                    <td className="py-3">
                      <StatusBadge status={role.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
