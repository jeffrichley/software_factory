import { Unknown } from "./Unknown";

/** A session's "now: …" headline: what its latest event shows it doing, or “—” before it does anything. */
export function NowLine({ now }: { now: string | null }) {
  return (
    <span className="now">
      <span className="now-k">now:</span>
      {now ?? <Unknown />}
    </span>
  );
}
