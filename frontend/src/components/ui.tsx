import { useEffect, type ReactNode } from "react";
import { AlertTriangle, Loader2, X } from "lucide-react";

export function Spinner({ label }: { label?: string }) {
  return <span className="spinner" role="status" aria-live="polite"><Loader2 size={16} className="spin" aria-hidden />{label && <span>{label}</span>}</span>;
}

export function Card({ title, action, children, className = "" }: { title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(title || action) && <header className="card-head"><h2>{title}</h2>{action}</header>}
      {children}
    </section>
  );
}

export function Badge({ tone = "neutral", children }: { tone?: "neutral" | "ok" | "warn" | "bad" | "info"; children: ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="note note-bad" role="alert">
      <AlertTriangle size={16} aria-hidden /> <span>{message}</span>
      {onRetry && <button className="link" onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function Empty({ icon, title, hint, children }: { icon?: ReactNode; title: string; hint?: string; children?: ReactNode }) {
  return <div className="empty">{icon}<strong>{title}</strong>{hint && <p>{hint}</p>}{children}</div>;
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="page-head">
      <div><h1>{title}</h1>{subtitle && <p className="muted">{subtitle}</p>}</div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  return (
    <div className="modal-back" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <header className="card-head"><h2>{title}</h2><button className="icon-btn" onClick={onClose} aria-label="Close"><X size={18} /></button></header>
        {children}
      </div>
    </div>
  );
}

export function GroupPicker({ groups, selected, onChange, disabled }: { groups: string[]; selected: string[]; onChange: (g: string[]) => void; disabled?: boolean }) {
  if (groups.length === 0) return <p className="muted small">No groups available yet.</p>;
  return (
    <div className="chips" role="group" aria-label="Groups">
      {groups.map((g) => {
        const on = selected.includes(g);
        return (
          <label key={g} className={`chip-toggle ${on ? "on" : ""}`}>
            <input type="checkbox" checked={on} disabled={disabled}
              onChange={() => onChange(on ? selected.filter((x) => x !== g) : [...selected, g])} />
            {g}
          </label>
        );
      })}
    </div>
  );
}
