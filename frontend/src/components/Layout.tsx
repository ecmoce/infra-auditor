import { NavLink, Outlet } from "react-router-dom";
import { clsx } from "clsx";

const links = [
  { to: "/", label: "Mission Control", icon: "🎯" },
  { to: "/compliance", label: "Compliance", icon: "📊" },
  { to: "/servers", label: "Servers", icon: "🖥️" },
  { to: "/regions", label: "Regions", icon: "🌍" },
  { to: "/config-drift", label: "Config Drift", icon: "🔍" },
  { to: "/alerts", label: "Alerts", icon: "🔔" },
] as const;

export function Layout() {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-[var(--color-surface)]/80 backdrop-blur-md border-b border-[var(--color-border)]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-xl">🛡️</span>
            <h1 className="text-base font-bold tracking-tight">Infra Auditor</h1>
          </div>
          <nav className="hidden sm:flex items-center gap-1">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.to === "/"}
                className={({ isActive }) =>
                  clsx(
                    "px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                    isActive
                      ? "bg-[var(--color-accent)] text-white"
                      : "text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-2)]"
                  )
                }
              >
                {l.icon} {l.label}
              </NavLink>
            ))}
          </nav>
        </div>
        {/* Mobile nav */}
        <nav className="sm:hidden flex border-t border-[var(--color-border)]">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to === "/"}
              className={({ isActive }) =>
                clsx(
                  "flex-1 text-center py-2 text-xs font-medium transition-colors",
                  isActive
                    ? "text-[var(--color-accent)] border-b-2 border-[var(--color-accent)]"
                    : "text-[var(--color-text-muted)]"
                )
              }
            >
              <div>{l.icon}</div>
              {l.label}
            </NavLink>
          ))}
        </nav>
      </header>

      {/* Main content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
