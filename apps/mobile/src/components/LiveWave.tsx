import { useEffect, useRef } from "react";

interface Props {
  /** Returns the current microphone level in 0..1. */
  getLevel: () => number;
  active: boolean;
}

const BARS = 40;

/**
 * Canvas waveform that scrolls while recording. Drawing on a canvas keeps
 * the per-frame animation off React's render path.
 */
export function LiveWave({ getLevel, active }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const history = useRef<number[]>(new Array(BARS).fill(0));
  const frame = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let width = 0;
    let height = 0;
    let color = "rgba(124, 108, 255, 0.9)";

    const resize = () => {
      const ratio = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      width = rect.width;
      height = rect.height;
      canvas.width = Math.max(1, Math.round(width * ratio));
      canvas.height = Math.max(1, Math.round(height * ratio));
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      color =
        getComputedStyle(canvas).getPropertyValue("--wave-color").trim() ||
        color;
    };

    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    resize();

    const draw = () => {
      ctx.clearRect(0, 0, width, height);
      const gap = 3;
      const barWidth = Math.max(2, (width - gap * (BARS - 1)) / BARS);
      const mid = height / 2;
      const gradient = ctx.createLinearGradient(0, 0, 0, height);
      gradient.addColorStop(0, color);
      gradient.addColorStop(0.5, color);
      gradient.addColorStop(1, "rgba(62, 198, 255, 0.55)");
      ctx.fillStyle = gradient;

      for (let i = 0; i < BARS; i += 1) {
        const level = history.current[i] ?? 0;
        const barHeight = Math.max(3, level * height * 0.92);
        const x = i * (barWidth + gap);
        const y = mid - barHeight / 2;
        ctx.beginPath();
        ctx.roundRect(x, y, barWidth, barHeight, barWidth / 2);
        ctx.fill();
      }

      if (active) {
        history.current.shift();
        const level = Math.min(1, getLevel());
        const smoothed = history.current[BARS - 2] ?? 0;
        history.current.push(smoothed * 0.45 + level * 0.55);
        frame.current = requestAnimationFrame(draw);
      }
    };

    if (active) {
      frame.current = requestAnimationFrame(draw);
    } else {
      history.current = new Array(BARS).fill(0.04);
      draw();
    }

    return () => {
      cancelAnimationFrame(frame.current);
      observer.disconnect();
    };
  }, [active, getLevel]);

  return (
    <canvas
      ref={canvasRef}
      className="live-wave"
      role="img"
      aria-label="Уровень громкости записи"
    />
  );
}
