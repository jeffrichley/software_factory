import type { ReactNode } from "react";
import { Icon, type IconName } from "./Icon";

export function Panel({ title, children, label }: { title?: ReactNode; children: ReactNode; label?: string }) {
  return (
    <div className="panel" aria-label={label}>
      {title ? <h4>{title}</h4> : null}
      {children}
    </div>
  );
}

export function SectionHeading({ children, icon, tone }: { children: ReactNode; icon?: IconName; tone?: "done" | "needs" }) {
  return (
    <h3 className={`sec-h${tone ? ` tone-${tone}` : ""}`}>
      {icon ? <Icon name={icon} /> : null}
      {children}
    </h3>
  );
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return <span className="eyebrow">{children}</span>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}
