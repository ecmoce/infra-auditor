import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Card, StatCard } from "../components/Card";
import { ComplianceGauge } from "../components/ComplianceGauge";
import { ScoreDisplay } from "../components/StatusBadge";
import { Loading, ErrorDisplay, EmptyState } from "../components/Loading";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

function barColor(score: number) {
  if (score >= 80) return "#22c55e";
  if (score >= 60) return "#eab308";
  return "#ef4444";
}

export function RegionDetail() {
  const { region } = useParams<{ region: string }>();

  const { data, isLoading, error } = useQuery({
    queryKey: ["region", region],
    queryFn: () => api.getRegionDetail(region!),
    enabled: !!region,
    refetchInterval: 30_000,
  });

  if (isLoading) return <Loading />;
  if (error) return <ErrorDisplay message={(error as Error).message} />;
  if (!data) return <EmptyState message="해당 지역 데이터가 없습니다" />;

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div>
        <Link to="/" className="text-sm text-[var(--color-accent)] hover:underline">
          ← Mission Control
        </Link>
        <h2 className="text-xl font-bold mt-2 capitalize">{data.region} Region</h2>
        <p className="text-sm text-[var(--color-text-muted)] mt-1">
          지역별 상세 컴플라이언스 현황
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="서버 수" value={data.total_servers} icon="🖥️" />
        <StatCard
          label="평균 컴플라이언스"
          value={`${data.average_compliance}%`}
          icon="📊"
          color={
            data.average_compliance >= 80
              ? "text-green-400"
              : data.average_compliance >= 60
                ? "text-yellow-400"
                : "text-red-400"
          }
        />
        <StatCard
          label="Critical"
          value={data.critical_issues}
          icon="💥"
          color={data.critical_issues > 0 ? "text-red-400" : "text-green-400"}
        />
        <StatCard
          label="Warning"
          value={data.warning_issues}
          icon="⚠️"
          color={data.warning_issues > 0 ? "text-yellow-400" : "text-green-400"}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title="컴플라이언스 점수">
          <div className="flex justify-center py-4">
            <ComplianceGauge score={data.average_compliance} size={140} />
          </div>
        </Card>

        <Card title="역할별 현황" className="lg:col-span-2">
          {data.roles.length === 0 ? (
            <EmptyState message="역할 데이터 없음" />
          ) : (
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.roles} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="name" tick={{ fill: "var(--color-text-muted)", fontSize: 12 }} />
                  <YAxis domain={[0, 100]} tick={{ fill: "var(--color-text-muted)", fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{
                      background: "var(--color-surface)",
                      border: "1px solid var(--color-border)",
                      borderRadius: "8px",
                      color: "var(--color-text)",
                      fontSize: "12px",
                    }}
                    formatter={(value: unknown) => [`${value}%`, "Compliance"]}
                  />
                  <Bar dataKey="compliance" radius={[4, 4, 0, 0]}>
                    {data.roles.map((entry) => (
                      <Cell key={entry.name} fill={barColor(entry.compliance)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
      </div>

      {/* Server list */}
      <Card title={`서버 목록 (${data.servers.length})`}>
        {data.servers.length === 0 ? (
          <EmptyState message="서버 데이터 없음" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
                  <th className="pb-3 font-medium">서버</th>
                  <th className="pb-3 font-medium">역할</th>
                  <th className="pb-3 font-medium text-right">점수</th>
                  <th className="pb-3 font-medium text-right">Critical</th>
                  <th className="pb-3 font-medium text-right">Warning</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)]">
                {data.servers.map((s) => (
                  <tr
                    key={s.server_id}
                    className="hover:bg-[var(--color-surface-2)] transition-colors"
                  >
                    <td className="py-3">
                      <Link
                        to={`/host/${encodeURIComponent(s.server_id)}`}
                        className="text-[var(--color-accent)] hover:underline"
                      >
                        {s.hostname}
                      </Link>
                    </td>
                    <td className="py-3 capitalize">{s.role}</td>
                    <td className="py-3 text-right">
                      <ScoreDisplay score={s.compliance_score} />
                    </td>
                    <td className="py-3 text-right">
                      {s.critical_issues > 0 ? (
                        <span className="text-red-400 font-medium">{s.critical_issues}</span>
                      ) : (
                        <span className="text-[var(--color-text-muted)]">0</span>
                      )}
                    </td>
                    <td className="py-3 text-right">
                      {s.warning_issues > 0 ? (
                        <span className="text-yellow-400 font-medium">{s.warning_issues}</span>
                      ) : (
                        <span className="text-[var(--color-text-muted)]">0</span>
                      )}
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
