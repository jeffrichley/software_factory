import { Icon } from "./Icon";

/** The header's sound toggle: on, Needs you and Done play their sounds. */
export function SoundToggle({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      className={`btn btn-sound${on ? "" : " off"}`}
      aria-pressed={on}
      title={on ? "Mute sounds" : "Play sounds"}
      onClick={onToggle}
    >
      <Icon name="bell" />
      Sound {on ? "on" : "off"}
    </button>
  );
}
