import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Card } from "../components/Card";
import { ScoreDisplay } from "../components/StatusBadge";
import { ComplianceGauge } from "../components/ComplianceGauge";
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
  PieChart,
  Pie,
} from "recharts";

function barColor(score: number) {
  if (score >= 80) return "#22c55e";
  if (score >= 60) return "#eab308";
  return "#ef4444";
}

export function Compliance() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["compliance"],
    queryFn: api.getCompliance,
    refetchInterval: 30_000,
  });

  if (isLoading) return <Loading />;
  if (error) return <ErrorDisplay message={(error as Error).message} />;
  if (!data) return <EmptyState message="데이터가 없습니다" />;

  const pieData = [
    { name: "Pass (≥80%)", value: data.distribution.pass, color: "#22c55e" },
    { name: "Warn (60-79%)", value: data.distribution.warn, color: "#eab308" },
    { name: "Fail (<60%)", value: data.distribution.fail, color: "#ef4444" },
  ].filter((d) => d.value > 0);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold">Compliance Overview</h2>
        <p className="text-sm text-[var(--color-text-muted)] mt-1">
          규칙별 컴플라이언스 상태 및 분포
        </p>
      </div>

      {/* Summary row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card title="전체 점수">
          <div className="flex justify-center py-2">
            <ComplianceGauge score={data.average_score} size={140} />
          </div>
          <p className="text-center text-xs text-[var(--color-text-muted)] mt-2">
            {data.total_servers}개 서버 평균
          </p>
        </Card>

        <Card title="상태 분포">
          <div className="h-44 flex items-center justify-center">
            {pieData.length === 0 ? (
              <EmptyState message="데이터 없음" />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={40}
                    outerRadius={65}
                    dataKey="value"
                    stroke="none"
                  >
                    {pieData.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      background: "var(--color-surface)",
                      border: "1px solid var(--color-border)",
                      borderRadius: "8px",
                      color: "var(--color-text)",
                      fontSize: "12px",
                    }}
                    formatter={(value: unknown) => [`${value} servers`, ""]}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
          <div className="flex justify-center gap-4 text-xs">
            {pieData.map((d) => (
              <div key={d.name} className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full" style={{ background: d.color }} />
                <span className="text-[var(--color-text-muted)]">
                  {d.name}: {d.value}
                </span>
              </div>
            ))}
          </div>
        </Card>

        <Card title="빠른 요약">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-[var(--color-text-muted)]">🟢 양호 (≥80%)</span>
              <span className="font-bold text-green-400">{data.distribution.pass}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-[var(--color-text-muted)]">🟡 경고 (60-79%)</span>
              <span className="font-bold text-yellow-400">{data.distribution.warn}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-[var(--color-text-muted)]">🔴 위험 (&lt;60%)</span>
              <span className="font-bold text-red-400">{data.distribution.fail}</span>
            </div>
            <hr className="border-[var(--color-border)]" />
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">전체</span>
              <span className="font-bold">{data.total_servers}</span>
            </div>
          </div>
        </Card>
      </div>

      {/* Region bar chart */}
      <Card title="지역별 컴플라이언스">
        {data.by_region.length === 0 ? (
          <EmptyState message="지역 데이터 없음" />
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.by_region} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="region" tick={{ fill: "var(--color-text-muted)", fontSize: 12 }} />
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
                <Bar dataKey="average_score" radius={[4, 4, 0, 0]}>
                  {data.by_region.map((entry) => (
                    <Cell key={entry.region} fill={barColor(entry.average_score)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      {/* Role bar chart */}
      <Card title="역할별 컴플라이언스">
        {data.by_role.length === 0 ? (
          <EmptyState message="역할 데이터 없음" />
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.by_role} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="role" tick={{ fill: "var(--color-text-muted)", fontSize: 12 }} />
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
                <Bar dataKey="average_score" radius={[4, 4, 0, 0]}>
                  {data.by_role.map((entry) => (
                    <Cell key={entry.role} fill={barColor(entry.average_score)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      {/* Heatmap table */}
      <Card title="지역 × 역할 매트릭스">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
                <th className="pb-3 font-medium">지역</th>
                <th className="pb-3 font-medium text-right">서버 수</th>
                <th className="pb-3 font-medium text-right">평균 점수</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)]">
              {data.by_region.map((r) => (
                <tr key={r.region} className="hover:bg-[var(--color-surface-2)] transition-colors">
                  <td className="py-3 capitalize">{r.region}</td>
                  <td className="py-3 text-right tabular-nums">{r.servers}</td>
                  <td className="py-3 text-right">
                    <ScoreDisplay score={r.average_score} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
