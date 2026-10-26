import type { ReactNode } from "react";

export type TagTone = "plain" | "frontier" | "blocked" | "struggle" | "needs" | "unknown";

export function Tag({ tone = "plain", children }: { tone?: TagTone; children: ReactNode }) {
  return <span className={tone === "plain" ? "tag" : `tag tag-${tone}`}>{children}</span>;
}
