const API_BASE = import.meta.env.VITE_API_URL ?? "/api/v1";

export interface ApiResponse<T> {
  status: "success" | "error";
  data: T;
  meta: { timestamp: string; version: string; request_id: string };
  error?: { code: string; message: string; details?: unknown };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  const json: ApiResponse<T> = await res.json();
  if (json.status === "error") {
    throw new Error(json.error?.message ?? "Unknown API error");
  }
  return json.data;
}

/* ─── Types ─────────────────────────────────────────── */

export interface DashboardSummary {
  overall: {
    total_servers: number;
    average_compliance: number;
    critical_issues: number;
    warning_issues: number;
    last_updated: string;
  };
  regions: RegionSummary[];
  roles: RoleSummary[];
}

export interface RegionSummary {
  name: string;
  servers: number;
  compliance: number;
  status: "healthy" | "warning" | "critical";
}

export interface RoleSummary {
  name: string;
  servers: number;
  compliance: number;
  status: "healthy" | "warning" | "critical";
}

export interface RegionDetail {
  region: string;
  total_servers: number;
  average_compliance: number;
  critical_issues: number;
  warning_issues: number;
  roles: { name: string; servers: number; compliance: number }[];
  servers: ServerEntry[];
}

export interface ServerEntry {
  server_id: string;
  hostname: string;
  role: string;
  region?: string;
  last_scan?: string;
  compliance_score: number;
  critical_issues: number;
  warning_issues: number;
  info_issues?: number;
}

export interface ServerListResponse {
  servers: ServerEntry[];
  pagination: {
    page: number;
    size: number;
    total: number;
    total_pages: number;
  };
}

export interface ComplianceSummary {
  total_servers: number;
  average_score: number;
  distribution: { pass: number; warn: number; fail: number };
  by_region: { region: string; servers: number; average_score: number }[];
  by_role: { role: string; servers: number; average_score: number }[];
}

export interface HostReport {
  current_report: Record<string, unknown>;
  report_id: string;
  received_at: string;
  history?: { report_id: string; timestamp: string; compliance_score: number }[];
}

export interface HealthStatus {
  service: string;
  version: string;
  database: string;
  timestamp: string;
  total_reports: number;
  unique_servers: number;
  last_report_received: string | null;
}

/* ─── API Functions ─────────────────────────────────── */

export const api = {
  getDashboard: () => request<DashboardSummary>("/dashboard"),

  getRegionDetail: (region: string) =>
    request<RegionDetail>(`/dashboard/${encodeURIComponent(region)}`),

  getCompliance: () => request<ComplianceSummary>("/compliance"),

  getServers: (params?: { region?: string; role?: string; page?: number; size?: number }) => {
    const sp = new URLSearchParams();
    if (params?.region) sp.set("region", params.region);
    if (params?.role) sp.set("role", params.role);
    if (params?.page) sp.set("page", String(params.page));
    if (params?.size) sp.set("size", String(params.size));
    const qs = sp.toString();
    return request<ServerListResponse>(`/reports${qs ? `?${qs}` : ""}`);
  },

  getHostReport: (serverId: string, includeHistory = false) =>
    request<HostReport>(
      `/reports/${encodeURIComponent(serverId)}?include_history=${includeHistory}&limit=20`
    ),

  getHealth: () => request<HealthStatus>("/health"),
};
