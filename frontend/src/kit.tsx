// The small shared component kit: every section builds from these.
import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "normal" | "small";
};

export function Button({ variant = "secondary", size = "normal", className = "", ...rest }: ButtonProps) {
  return <button type="button" className={`btn btn-${variant} btn-${size} ${className}`} {...rest} />;
}

export function Card({ title, actions, children }: { title?: ReactNode; actions?: ReactNode; children: ReactNode }) {
  return (
    <section className="card">
      {(title || actions) && (
        <header className="card-header">
          {title && <h2>{title}</h2>}
          {actions && <div className="card-actions">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      {children}
    </div>
  );
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}

export function Toolbar({ children }: { children: ReactNode }) {
  return <div className="toolbar">{children}</div>;
}

/** A 0..1 value with a label; turns to a warning past `warnAbove`. */
export function Meter({ value, label, warnAbove = 1 }: { value: number; label: string; warnAbove?: number }) {
  const percent = Math.round(Math.min(Math.max(value, 0), 1) * 100);
  return (
    <div className={`meter ${value >= warnAbove ? "meter-warn" : ""}`} title={label}>
      <div className="meter-track">
        <div className="meter-fill" style={{ width: `${percent}%` }} />
      </div>
      <span className="meter-label">{label}</span>
    </div>
  );
}

export function Badge({ tone, children }: { tone: "ok" | "warning" | "error" | "neutral"; children: ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function ErrorNote({ error, onClose }: { error: string | null; onClose?: () => void }) {
  if (!error) return null;
  return (
    <div className="error-note" role="alert">
      <span>{error}</span>
      {onClose && (
        <Button variant="ghost" size="small" onClick={onClose} aria-label="Dismiss">
          ×
        </Button>
      )}
    </div>
  );
}
