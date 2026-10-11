/** Tween a number from `from` to `to` over `ms` with requestAnimationFrame; returns a cancel function.
 *  Jumps straight to `to` when ms <= 0 or when requestAnimationFrame is unavailable (tests, reduced motion). */
export function countUp(from: number, to: number, ms: number, onFrame: (v: number) => void): () => void {
  if (ms <= 0 || typeof requestAnimationFrame === "undefined") {
    onFrame(to);
    return () => {};
  }
  const start = performance.now();
  let raf = 0;
  const step = (now: number) => {
    const p = Math.min(1, (now - start) / ms);
    const eased = 1 - Math.pow(1 - p, 3);
    onFrame(from + (to - from) * eased);
    if (p < 1) raf = requestAnimationFrame(step);
  };
  raf = requestAnimationFrame(step);
  return () => cancelAnimationFrame(raf);
}
