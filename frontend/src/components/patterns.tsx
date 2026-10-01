import { ReactNode } from "react";
import { Link } from "react-router-dom";
import { SurfaceCard } from "./ui";

function classNames(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}


export function BrandMark() {
  return (
    <div className="prototype-login-logo brand-mark-compass" aria-hidden="true">
      <span className="brand-mark-plane">✈️</span>
    </div>
  );
}

export function HomeSectionHeader({ actionLabel, title, to }: { actionLabel?: string; title: string; to?: string }) {
  return (
    <div className="ds-section-header">
      <h3>{title}</h3>
      {actionLabel && to && <Link to={to}>{actionLabel}</Link>}
    </div>
  );
}

export function HomeRail({ ariaLabel, children, className, title }: { ariaLabel?: string; children: ReactNode; className?: string; title: string }) {
  return (
    <section className={classNames("ds-home-rail", className)} aria-label={ariaLabel ?? title}>
      <HomeSectionHeader title={title} />
      <div className="ds-home-rail-items">{children}</div>
    </section>
  );
}

export function AuthFormShell({
  body,
  children,
  showBrandMark = true,
  title,
}: {
  body?: string;
  children: ReactNode;
  showBrandMark?: boolean;
  title: string;
}) {
  return (
    <section className="ds-auth-form-shell">
      <div className="ds-auth-form-head">
        {showBrandMark && <BrandMark />}
        <h1>{title}</h1>
        {body && <p>{body}</p>}
      </div>
      {children}
    </section>
  );
}

export function ProfilePanel({ children, meta, title }: { children: ReactNode; meta?: string; title: string }) {
  return (
    <SurfaceCard as="section" className="ds-profile-panel">
      <div className="ds-profile-panel-head">
        <div>
          <h2>{title}</h2>
          {meta && <p className="meta">{meta}</p>}
        </div>
      </div>
      {children}
    </SurfaceCard>
  );
}

export function ProfileSetupStep({
  body,
  children,
  eyebrow,
  title,
}: {
  body: string;
  children: ReactNode;
  eyebrow: string;
  title: string;
}) {
  return (
    <SurfaceCard className="ds-profile-setup-step">
      <div className="eyebrow">{eyebrow}</div>
      <h2>{title}</h2>
      <p>{body}</p>
      <div className="choice-grid">{children}</div>
    </SurfaceCard>
  );
}
