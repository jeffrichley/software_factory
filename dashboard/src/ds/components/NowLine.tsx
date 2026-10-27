import { Unknown } from "./Unknown";

/** A session's "now: …" headline: what its latest event shows it doing, in a few words, or “—” before it does anything.
 * `detail` is what the headline leaves out (e.g. the full command), shown on hover. */
export function NowLine({ now, detail }: { now: string | null; detail?: string | null }) {
  return (
    <span className="now" title={now && detail ? detail : undefined}>
      <span className="now-k">now:</span>
      {now ?? <Unknown />}
    </span>
  );
}
