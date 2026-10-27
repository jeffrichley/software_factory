/** Sounds the server schedules (one per transition): Needs you, and a softer Done. */
export type SoundName = "needs_you" | "done";

/**
 * The sounds to play from the server's latest list, given the highest id already heard.
 * Ids only grow. When the page opens (nothing heard yet) none play: they are from before.
 */
export function newSounds<S extends { id: number }>(sounds: S[], heard: number | undefined): { play: S[]; heard: number } {
  const latest = Math.max(heard ?? 0, ...sounds.map((s) => s.id));
  if (heard === undefined) return { play: [], heard: latest };
  return { play: sounds.filter((s) => s.id > heard), heard: latest };
}

/** Each sound's notes (Hz), gain and note length: Needs you is a brighter rising pair, Done one soft low note. */
const TONES: Record<SoundName, { notes: number[]; gain: number; noteS: number }> = {
  needs_you: { notes: [880, 1175], gain: 0.25, noteS: 0.16 },
  done: { notes: [523], gain: 0.08, noteS: 0.45 },
};

let audio: AudioContext | undefined;

/** Synthesised, so the bundle ships no audio files. Silent if the browser blocks audio. */
export function playSound(name: SoundName): void {
  try {
    audio ??= new AudioContext();
    const { notes, gain, noteS } = TONES[name];
    notes.forEach((hz, i) => {
      const start = audio!.currentTime + i * noteS;
      const osc = audio!.createOscillator();
      const env = audio!.createGain();
      osc.type = "sine";
      osc.frequency.value = hz;
      env.gain.setValueAtTime(0.0001, start);
      env.gain.exponentialRampToValueAtTime(gain, start + 0.02);
      env.gain.exponentialRampToValueAtTime(0.0001, start + noteS);
      osc.connect(env).connect(audio!.destination);
      osc.start(start);
      osc.stop(start + noteS);
    });
  } catch {
    // No audio available: the dashboard still shows the state.
  }
}
