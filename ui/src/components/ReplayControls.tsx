const SPEEDS = [1, 2, 4, 8];

export function ReplayControls({ playing, speed, onPlay, onPause, onSpeed, disabled }: {
  playing: boolean; speed: number; onPlay: () => void; onPause: () => void; onSpeed: (n: number) => void; disabled: boolean;
}) {
  return (
    <div className="flex items-center gap-2 font-mono text-xs">
      <button
        type="button"
        onClick={playing ? onPause : onPlay}
        disabled={disabled}
        className="h-8 w-20 rounded border border-line bg-bg text-text transition-colors duration-150 hover:border-accent disabled:cursor-not-allowed disabled:opacity-40"
        aria-label={playing ? "Pause replay" : "Play replay"}
      >
        {playing ? "❚❚ PAUSE" : "▶ PLAY"}
      </button>
      <div className="flex overflow-hidden rounded border border-line" role="group" aria-label="Replay speed">
        {SPEEDS.map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => onSpeed(n)}
            aria-pressed={speed === n}
            className={`h-8 w-10 transition-colors duration-150 ${speed === n ? "bg-accent text-bg" : "bg-bg text-muted hover:text-text"}`}
          >
            {n}×
          </button>
        ))}
      </div>
    </div>
  );
}
