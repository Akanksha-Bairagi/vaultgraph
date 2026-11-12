import { useState, type ReactNode } from "react";
import { Cpu, FileText, LayoutDashboard, LogOut, Menu, MessageSquareText, Network, ScrollText, ShieldCheck, Users, X } from "lucide-react";
import { useAuth } from "../auth.tsx";
import { navigate, useAsync, type Route } from "../hooks.ts";
import { api } from "../lib/client.ts";
import { initials } from "../lib/format.ts";

const NAV: { to: Route; label: string; icon: ReactNode; admin?: boolean }[] = [
  { to: "/", label: "Overview", icon: <LayoutDashboard size={18} /> },
  { to: "/ask", label: "Ask", icon: <MessageSquareText size={18} /> },
  { to: "/documents", label: "Documents", icon: <FileText size={18} /> },
  { to: "/graph", label: "Knowledge graph", icon: <Network size={18} /> },
  { to: "/people", label: "People & groups", icon: <Users size={18} />, admin: true },
  { to: "/audit", label: "Audit log", icon: <ScrollText size={18} />, admin: true },
];

export function Layout({ route, children }: { route: Route; children: ReactNode }) {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const status = useAsync(() => api.status(), []);
  const llm = status.data?.llm;
  const go = (r: Route) => { navigate(r); setOpen(false); };
  const tone = !llm ? "idle" : llm.healthy === false ? "bad" : llm.provider === "mock" ? "warn" : "ok";

  return (
    <div className="app">
      <aside className={`sidebar ${open ? "open" : ""}`} aria-label="Primary">
        <div className="brand"><ShieldCheck size={22} aria-hidden /><span>VaultGraph</span>
          <button className="icon-btn only-mobile" onClick={() => setOpen(false)} aria-label="Close menu"><X size={18} /></button>
        </div>
        <nav>
          {NAV.filter((n) => !n.admin || user?.role === "admin").map((n) => (
            <a key={n.to} href={`#${n.to}`} className={`nav-item ${route === n.to ? "active" : ""}`} aria-current={route === n.to ? "page" : undefined}
              onClick={(e) => { e.preventDefault(); go(n.to); }}>{n.icon}<span>{n.label}</span></a>
          ))}
        </nav>
        <div className="side-foot">
          <div className={`pill pill-${tone}`} title={llm?.detail}>
            <Cpu size={14} aria-hidden />
            <span>{llm ? (llm.provider === "groq" ? `Groq · ${llm.model.split("/").pop()}` : "Offline mock LLM") : "Checking…"}</span>
          </div>
          <div className="me">
            <div className="avatar" aria-hidden>{initials(user?.email ?? "")}</div>
            <div className="me-text"><strong title={user?.email}>{user?.email}</strong><span>{user?.org_name} · {user?.role}</span></div>
            <button className="icon-btn" onClick={logout} aria-label="Sign out" title="Sign out"><LogOut size={17} /></button>
          </div>
        </div>
      </aside>
      {open && <div className="scrim" onClick={() => setOpen(false)} />}
      <div className="main">
        <header className="topbar">
          <button className="icon-btn" onClick={() => setOpen(true)} aria-label="Open menu"><Menu size={20} /></button>
          <div className="brand-sm"><ShieldCheck size={18} />VaultGraph</div>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
