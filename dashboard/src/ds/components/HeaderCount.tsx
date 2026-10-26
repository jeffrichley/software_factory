import { Icon } from "./Icon";

/** Header count of sessions that Need you; hot (amber) when any do. */
export function NeedsCount({ count }: { count: number }) {
  return (
    <span className={`count count-needs${count ? " hot" : ""}`}>
      {count ? <Icon name="alert" /> : null}
      <b>{count}</b>Needs you
    </span>
  );
}

export function DoneUnseenCount({ count }: { count: number }) {
  return (
    <span className="count count-done">
      <span className="dot dot-done" />
      <b>{count}</b>Done unseen
    </span>
  );
}

/** "+N Needs you on hidden Machines": hidden Machines never hide alerts. */
export function HiddenNeedsBadge({ count, onShow }: { count: number; onShow?: () => void }) {
  if (!count) return null;
  return (
    <button type="button" className="count count-hidden" title="Show the Machines these come from" onClick={onShow}>
      <Icon name="alert" />+{count} Needs you on hidden Machines
    </button>
  );
}
