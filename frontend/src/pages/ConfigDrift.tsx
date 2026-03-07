import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Card } from "../components/Card";
import { Loading, ErrorDisplay, EmptyState } from "../components/Loading";

export function ConfigDrift() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["config-drift"],
    queryFn: () => api.getConfigDrift(),
    refetchInterval: 30_000,
  });

  if (isLoading) return <Loading />;
  if (error) return <ErrorDisplay message={(error as Error).message} />;
  if (!data) return <EmptyState message="데이터 없음" />;

  const { groups, total_mismatches } = data;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold">설정 불일치 탐지</h2>
        <p className="text-sm text-[var(--color-text-muted)] mt-1">
          같은 역할 서버 간 설정값 비교 및 표준화 추천
        </p>
      </div>

      {/* Summary */}
      <div
        className={`rounded-xl p-4 ${
          total_mismatches > 0
            ? "bg-yellow-500/10 border border-yellow-500/30"
            : "bg-green-500/10 border border-green-500/30"
        }`}
      >
        <div className="flex items-center gap-2">
          <span className="text-lg">{total_mismatches > 0 ? "🔍" : "✅"}</span>
          <span className="text-sm font-semibold">
            {total_mismatches > 0
              ? `${total_mismatches}개의 설정 불일치 발견`
              : "모든 동일 역할 서버들이 일관된 설정을 유지하고 있습니다"}
          </span>
        </div>
      </div>

      {/* Groups */}
      {groups.length === 0 ? (
        <EmptyState message="비교할 동일 역할 서버 그룹이 없습니다 (역할당 최소 2대 필요)" />
      ) : (
        groups.map((g) => (
          <Card
            key={g.role}
            title={
              <div className="flex items-center justify-between w-full">
                <span className="capitalize">{g.role}</span>
                <span className="text-xs font-normal text-[var(--color-text-muted)]">
                  {g.server_count} servers · {g.mismatch_count} mismatches
                </span>
              </div>
            }
          >
            {/* Server list */}
            <div className="flex gap-2 flex-wrap mb-4">
              {g.servers.map((s) => (
                <span
                  key={s.server_id}
                  className="text-xs bg-[var(--color-surface-2)] px-2 py-1 rounded"
                >
                  {s.hostname} ({s.region})
                </span>
              ))}
            </div>

            {g.mismatch_count === 0 ? (
              <p className="text-sm text-green-400">✅ 모든 설정이 일치합니다</p>
            ) : (
              <div className="space-y-3">
                {g.mismatches.map((m) => (
                  <div
                    key={m.rule}
                    className="bg-[var(--color-surface-2)] rounded-lg p-3"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium font-mono">{m.rule}</span>
                      <span
                        className={`text-xs px-2 py-0.5 rounded ${
                          m.severity === "critical"
                            ? "bg-red-500/20 text-red-400"
                            : m.severity === "warning"
                              ? "bg-yellow-500/20 text-yellow-400"
                              : "bg-blue-500/20 text-blue-400"
                        }`}
                      >
                        {m.severity}
                      </span>
                    </div>

                    <p className="text-xs text-[var(--color-text-muted)] mb-2">
                      기대 상태: <span className="text-green-400">{m.expected_status}</span>
                      {" · "}
                      {m.conforming_servers.length}/{m.total_checked} 서버 정상
                    </p>

                    <div className="space-y-1">
                      <p className="text-xs font-medium text-red-400">불일치 서버:</p>
                      {m.deviating_servers.map((ds) => (
                        <div
                          key={ds.server_id}
                          className="text-xs flex items-center gap-2 text-[var(--color-text-muted)]"
                        >
                          <span className="text-red-400">✗</span>
                          <span className="font-medium">{ds.server_id}</span>
                          <span>status: {ds.status}</span>
                          {ds.actual !== null && ds.actual !== undefined && (
                            <span className="font-mono">actual: {String(ds.actual)}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        ))
      )}
    </div>
  );
}
