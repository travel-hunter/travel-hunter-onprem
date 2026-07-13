import { ReactNode } from "react";
import { Link } from "react-router-dom";

type ButtonVariant = "primary" | "secondary" | "ghost" | "line" | "danger";
type Tone = "default" | "primary" | "warning" | "yellow" | "green" | "gray" | "benefit" | "confirmed" | "draft" | "danger";
type SurfaceTone = "default" | "draft" | "confirmed" | "benefit" | "danger";

function classNames(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

export function Button({
  children,
  variant = "primary",
  full = false,
  onClick,
  type = "button",
  disabled = false,
}: {
  children: ReactNode;
  variant?: ButtonVariant;
  full?: boolean;
  onClick?: () => void;
  type?: "button" | "submit";
  disabled?: boolean;
}) {
  return (
    <button className={classNames("btn", variant, full && "full")} disabled={disabled} onClick={onClick} type={type}>
      {children}
    </button>
  );
}

export function LinkButton({ children, to, variant = "primary", full = false }: { children: ReactNode; to: string; variant?: ButtonVariant; full?: boolean }) {
  return (
    <Link className={classNames("btn", variant, full && "full")} to={to}>
      {children}
    </Link>
  );
}

export function Tag({ children, tone = "default" }: { children: ReactNode; tone?: Tone }) {
  return <span className={classNames("tag", tone)}>{children}</span>;
}

export function SurfaceCard({
  children,
  tone = "default",
  className,
  as: Component = "div",
}: {
  children: ReactNode;
  tone?: SurfaceTone;
  className?: string;
  as?: "article" | "section" | "div";
}) {
  return <Component className={classNames("ds-card", tone !== "default" && tone, className)}>{children}</Component>;
}

export function StatusPanel({
  tone,
  badge,
  title,
  body,
  action,
  className,
  ariaLabel,
}: {
  tone: "draft" | "confirmed" | "benefit" | "danger";
  badge: string;
  title: string;
  body?: string;
  action?: ReactNode;
  className?: string;
  ariaLabel?: string;
}) {
  return (
    <section className={classNames("ds-status-panel", tone, className)} aria-label={ariaLabel ?? title}>
      <div>
        <span className={classNames("ds-status-badge", tone)}>{badge}</span>
        <strong>{title}</strong>
        {body && <p className="meta">{body}</p>}
      </div>
      {action && <div className="ds-status-action">{action}</div>}
    </section>
  );
}

export function TopBar({ title, left, right }: { title: string; left?: ReactNode; right?: ReactNode }) {
  return (
    <div className="top-bar">
      <div>{left}</div>
      <h1>{title}</h1>
      <div className="top-right">{right}</div>
    </div>
  );
}

export function PageHead({ eyebrow, title, body }: { eyebrow: string; title: string; body?: string }) {
  return (
    <div className="page-head">
      <div className="eyebrow">{eyebrow}</div>
      <h2>{title}</h2>
      {body && <p>{body}</p>}
    </div>
  );
}

export function IconButton({ children, to, label, onClick }: { children: ReactNode; to?: string; label: string; onClick?: () => void }) {
  if (to) {
    return (
      <Link className="icon-btn" to={to} aria-label={label}>
        {children}
      </Link>
    );
  }

  return (
    <button className="icon-btn" onClick={onClick} type="button" aria-label={label}>
      {children}
    </button>
  );
}

export function EmptyState({
  title,
  body,
  action,
  compact = false,
  eyebrow,
}: {
  title: string;
  body: string;
  action?: ReactNode;
  compact?: boolean;
  eyebrow?: string;
}) {
  return (
    <section className={compact ? "empty-state compact" : "empty-state"}>
      {eyebrow && <span className="state-eyebrow">{eyebrow}</span>}
      <h1>{title}</h1>
      <p>{body}</p>
      {action && <div className="state-actions">{action}</div>}
    </section>
  );
}

export function LoadingState({ label = "정보를 불러오는 중입니다", body, compact = false }: { label?: string; body?: string; compact?: boolean }) {
  return (
    <div className={compact ? "state-panel compact" : "state-panel"} role="status">
      <span className="spinner" />
      <strong>{label}</strong>
      {body && <p>{body}</p>}
    </div>
  );
}

export function ErrorState({
  message,
  action,
  compact = false,
  title = "문제가 생겼어요",
}: {
  message: string;
  action?: ReactNode;
  compact?: boolean;
  title?: string;
}) {
  return (
    <div className={compact ? "state-panel error compact" : "state-panel error"} role="alert">
      <strong>{title}</strong>
      <p>{message}</p>
      {action && <div className="state-actions">{action}</div>}
    </div>
  );
}

export function Toast({ children }: { children: ReactNode }) {
  return (
    <div className="toast" role="status">
      {children}
    </div>
  );
}

export function ConfirmDialog({
  open,
  title,
  body,
  error,
  confirmLabel,
  cancelLabel = "취소",
  isSubmitting = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  body: string;
  error?: string;
  confirmLabel: string;
  cancelLabel?: string;
  isSubmitting?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;

  const cancel = () => {
    if (!isSubmitting) onCancel();
  };

  return (
    <div className="sheet-backdrop confirm-backdrop" role="presentation" onMouseDown={cancel}>
      <section className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-dialog-title" onMouseDown={(event) => event.stopPropagation()}>
        <div>
          <h2 id="confirm-dialog-title">{title}</h2>
          <p>{body}</p>
          {error && <p className="form-error">{error}</p>}
        </div>
        <div className="confirm-actions">
          <Button variant="line" disabled={isSubmitting} onClick={cancel}>
            {cancelLabel}
          </Button>
          <Button variant="danger" disabled={isSubmitting} onClick={onConfirm}>
            {isSubmitting ? `${confirmLabel} 중` : confirmLabel}
          </Button>
        </div>
      </section>
    </div>
  );
}
