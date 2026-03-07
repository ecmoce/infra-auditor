import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Card } from "../components/Card";
import { ComplianceGauge } from "../components/ComplianceGauge";
import { StatusBadge, scoreToStatus } from "../components/StatusBadge";
import { Loading, ErrorDisplay, EmptyState } from "../components/Loading";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

function severityIcon(sev: string) {
  switch (sev) {
    case "critical":
      return "💥";
    case "warning":
      return "⚠️";
    case "info":
      return "ℹ️";
    default:
      return "📋";
  }
}

function severityColor(sev: string) {
  switch (sev) {
    case "critical":
      return "text-red-400";
    case "warning":
      return "text-yellow-400";
    case "info":
      return "text-blue-400";
    default:
      return "text-[var(--color-text-muted)]";
  }
}

export function HostDetail() {
  const { serverId } = useParams<{ serverId: string }>();

  const { data, isLoading, error } = useQuery({
    queryKey: ["host", serverId],
    queryFn: () => api.getHostReport(serverId!, true),
    enabled: !!serverId,
  });

  if (isLoading) return <Loading />;
  if (error) return <ErrorDisplay message={(error as Error).message} />;
  if (!data) return <EmptyState message="호스트 데이터가 없습니다" />;

  const report = data.current_report as Record<string, unknown>;
  const serverInfo = (report.server_info ?? {}) as Record<string, unknown>;
  const compliance = (report.compliance ?? {}) as Record<string, unknown>;
  const results = (report.results ?? []) as Array<Record<string, unknown>>;
  const severitySummary = (compliance.severity_summary ?? {}) as Record<string, number>;
  const overallScore = (compliance.overall_score ?? 0) as number;

  const role = serverInfo.role as Record<string, unknown> | string | undefined;
  const roleName = typeof role === "object" ? (role?.detected as string) ?? "unknown" : role ?? "unknown";

  // History data for trend chart
  const historyData = (data.history ?? [])
    .slice()
    .reverse()
    .map((h) => ({
      date: new Date(h.timestamp).toLocaleDateString("ko-KR", {
        month: "short",
        day: "numeric",
      }),
      score: h.compliance_score,
    }));

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div>
        <Link to="/servers" className="text-sm text-[var(--color-accent)] hover:underline">
          ← 서버 목록
        </Link>
        <h2 className="text-xl font-bold mt-2">
          {(serverInfo.hostname as string) ?? serverId}
        </h2>
        <p className="text-sm text-[var(--color-text-muted)] mt-1 capitalize">
          {roleName} · {(serverInfo.region as string) ?? "unknown"} ·{" "}
          <span className="text-xs">
            마지막 스캔: {new Date(data.received_at).toLocaleString("ko-KR")}
          </span>
        </p>
      </div>

      {/* Score + severity */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card title="컴플라이언스 점수">
          <div className="flex justify-center py-2">
            <ComplianceGauge score={overallScore} size={140} />
          </div>
          <div className="text-center mt-2">
            <StatusBadge status={scoreToStatus(overallScore)} />
          </div>
        </Card>

        <Card title="이슈 요약">
          <div className="space-y-4 py-2">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-sm">
                💥 <span className="text-red-400">Critical</span>
              </span>
              <span className="text-xl font-bold text-red-400 tabular-nums">
                {severitySummary.critical ?? 0}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-sm">
                ⚠️ <span className="text-yellow-400">Warning</span>
              </span>
              <span className="text-xl font-bold text-yellow-400 tabular-nums">
                {severitySummary.warning ?? 0}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-sm">
                ℹ️ <span className="text-blue-400">Info</span>
              </span>
              <span className="text-xl font-bold text-blue-400 tabular-nums">
                {severitySummary.info ?? 0}
              </span>
            </div>
          </div>
        </Card>

        <Card title="컴플라이언스 트렌드">
          {historyData.length < 2 ? (
            <div className="flex items-center justify-center h-40 text-sm text-[var(--color-text-muted)]">
              히스토리 데이터 부족
            </div>
          ) : (
            <div className="h-40">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={historyData} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="date" tick={{ fill: "var(--color-text-muted)", fontSize: 10 }} />
                  <YAxis
                    domain={[0, 100]}
                    tick={{ fill: "var(--color-text-muted)", fontSize: 10 }}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "var(--color-surface)",
                      border: "1px solid var(--color-border)",
                      borderRadius: "8px",
                      color: "var(--color-text)",
                      fontSize: "12px",
                    }}
                    formatter={(value: unknown) => [`${value}%`, "Score"]}
                  />
                  <Line
                    type="monotone"
                    dataKey="score"
                    stroke="var(--color-accent)"
                    strokeWidth={2}
                    dot={{ r: 3, fill: "var(--color-accent)" }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
      </div>

      {/* Detailed results */}
      <Card title="상세 검사 결과">
        {results.length === 0 ? (
          <EmptyState message="검사 결과 없음" />
        ) : (
          <div className="space-y-2">
            {results.map((item, idx) => {
              const sev = (item.severity as string) ?? "info";
              const status = (item.status as string) ?? "unknown";
              return (
                <div
                  key={idx}
                  className="flex items-start gap-3 p-3 rounded-lg bg-[var(--color-surface-2)] hover:bg-[var(--color-border)]/30 transition-colors"
                >
                  <span className="text-lg mt-0.5">{severityIcon(sev)}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{item.item as string}</span>
                      <StatusBadge
                        status={status === "pass" ? "pass" : status === "warn" ? "warn" : "fail"}
                        label={status}
                      />
                    </div>
                    {item.message != null && (
                      <p className="text-xs text-[var(--color-text-muted)] mt-1">
                        {String(item.message)}
                      </p>
                    )}
                    {(item.current !== undefined || item.recommended !== undefined) && (
                      <div className="flex gap-4 mt-1 text-xs">
                        {item.current !== undefined && (
                          <span>
                            현재: <code className={severityColor(sev)}>{String(item.current)}</code>
                          </span>
                        )}
                        {item.recommended !== undefined && (
                          <span>
                            권장: <code className="text-green-400">{String(item.recommended)}</code>
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
