const SPEEDS = [1, 2, 4, 8];

export function ReplayControls({ playing, done, speed, onPlay, onPause, onSpeed, disabled }: {
  playing: boolean; done: boolean; speed: number; onPlay: () => void; onPause: () => void; onSpeed: (n: number) => void; disabled: boolean;
}) {
  return (
    <div className="flex shrink-0 items-center gap-2 font-mono text-xs">
      <button
        type="button"
        onClick={playing ? onPause : onPlay}
        disabled={disabled}
        className="h-8 w-24 rounded border border-line bg-bg text-text transition-colors duration-150 enabled:hover:border-accent disabled:cursor-not-allowed disabled:opacity-40"
        aria-label={playing ? "Pause replay" : done ? "Replay from the start" : "Play replay"}
      >
        {playing ? "❚❚ PAUSE" : done ? "↻ AGAIN" : "▶ PLAY"}
      </button>
      {/* No overflow-hidden on the group: it would clip the focus ring. */}
      <div className="flex rounded border border-line" role="group" aria-label="Replay speed">
        {SPEEDS.map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => onSpeed(n)}
            aria-pressed={speed === n}
            className={`h-8 w-10 transition-colors duration-150 first:rounded-l last:rounded-r ${speed === n ? "bg-accent text-bg" : "bg-bg text-muted hover:text-text"}`}
          >
            {n}×
          </button>
        ))}
      </div>
    </div>
  );
}
