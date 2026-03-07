import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Card } from "../components/Card";
import { ScoreDisplay, StatusBadge, scoreToStatus } from "../components/StatusBadge";
import { Loading, ErrorDisplay, EmptyState } from "../components/Loading";

export function Servers() {
  const [region, setRegion] = useState<string>("");
  const [role, setRole] = useState<string>("");
  const [page, setPage] = useState(1);
  const size = 25;

  const { data, isLoading, error } = useQuery({
    queryKey: ["servers", region, role, page],
    queryFn: () =>
      api.getServers({
        region: region || undefined,
        role: role || undefined,
        page,
        size,
      }),
    refetchInterval: 30_000,
  });

  // Fetch dashboard for filter options
  const { data: dashboard } = useQuery({
    queryKey: ["dashboard"],
    queryFn: api.getDashboard,
    staleTime: 60_000,
  });

  const regions = dashboard?.regions.map((r) => r.name) ?? [];
  const roles = dashboard?.roles.map((r) => r.name) ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold">서버 목록</h2>
        <p className="text-sm text-[var(--color-text-muted)] mt-1">
          전체 서버 현황 및 필터링
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <select
          value={region}
          onChange={(e) => {
            setRegion(e.target.value);
            setPage(1);
          }}
          className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg px-3 py-2 text-sm text-[var(--color-text)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
        >
          <option value="">🌍 모든 지역</option>
          {regions.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>

        <select
          value={role}
          onChange={(e) => {
            setRole(e.target.value);
            setPage(1);
          }}
          className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg px-3 py-2 text-sm text-[var(--color-text)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
        >
          <option value="">🏷️ 모든 역할</option>
          {roles.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
      </div>

      {/* Server table */}
      {isLoading ? (
        <Loading />
      ) : error ? (
        <ErrorDisplay message={(error as Error).message} />
      ) : !data || data.servers.length === 0 ? (
        <EmptyState message="서버 데이터가 없습니다" />
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
                  <th className="pb-3 font-medium">서버</th>
                  <th className="pb-3 font-medium hidden sm:table-cell">역할</th>
                  <th className="pb-3 font-medium hidden md:table-cell">지역</th>
                  <th className="pb-3 font-medium text-right">점수</th>
                  <th className="pb-3 font-medium text-center hidden sm:table-cell">상태</th>
                  <th className="pb-3 font-medium text-right hidden md:table-cell">Last Scan</th>
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
                        className="text-[var(--color-accent)] hover:underline font-medium"
                      >
                        {s.hostname}
                      </Link>
                      <div className="sm:hidden text-xs text-[var(--color-text-muted)] mt-0.5 capitalize">
                        {s.role} · {s.region}
                      </div>
                    </td>
                    <td className="py-3 capitalize hidden sm:table-cell">{s.role}</td>
                    <td className="py-3 capitalize hidden md:table-cell">{s.region}</td>
                    <td className="py-3 text-right">
                      <ScoreDisplay score={s.compliance_score} />
                    </td>
                    <td className="py-3 text-center hidden sm:table-cell">
                      <StatusBadge status={scoreToStatus(s.compliance_score)} />
                    </td>
                    <td className="py-3 text-right text-xs text-[var(--color-text-muted)] hidden md:table-cell">
                      {s.last_scan
                        ? new Date(s.last_scan).toLocaleString("ko-KR", {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {data.pagination.total_pages > 1 && (
            <div className="flex items-center justify-between mt-4 pt-4 border-t border-[var(--color-border)]">
              <p className="text-xs text-[var(--color-text-muted)]">
                {data.pagination.total}개 서버 중 {(page - 1) * size + 1}-
                {Math.min(page * size, data.pagination.total)}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  ← 이전
                </button>
                <span className="px-3 py-1.5 text-xs tabular-nums">
                  {page} / {data.pagination.total_pages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(data.pagination.total_pages, p + 1))}
                  disabled={page === data.pagination.total_pages}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  다음 →
                </button>
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
