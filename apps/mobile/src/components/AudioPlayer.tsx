import { type CSSProperties, useEffect, useRef, useState } from "react";

import { formatClock } from "../lib/format";
import { Icon } from "./Icon";

interface Props {
  src: string;
}

/** Minimal custom player: play/pause, seekable progress, elapsed/total. */
export function AudioPlayer({ src }: Props) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [current, setCurrent] = useState(0);
  const [error, setError] = useState(false);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const onLoaded = () =>
      setDuration(Number.isFinite(audio.duration) ? audio.duration : 0);
    const onTime = () => setCurrent(audio.currentTime);
    const onEnd = () => {
      setPlaying(false);
      setCurrent(0);
    };
    const onError = () => setError(true);
    audio.addEventListener("loadedmetadata", onLoaded);
    audio.addEventListener("timeupdate", onTime);
    audio.addEventListener("ended", onEnd);
    audio.addEventListener("error", onError);
    return () => {
      audio.removeEventListener("loadedmetadata", onLoaded);
      audio.removeEventListener("timeupdate", onTime);
      audio.removeEventListener("ended", onEnd);
      audio.removeEventListener("error", onError);
      audio.pause();
    };
  }, []);

  const toggle = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) {
      void audio
        .play()
        .then(() => setPlaying(true))
        .catch(() => setError(true));
    } else {
      audio.pause();
      setPlaying(false);
    }
  };

  const seek = (value: number) => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = value;
    setCurrent(value);
  };

  const progress = duration > 0 ? (current / duration) * 100 : 0;

  return (
    <div className={`player${error ? " player-error" : ""}`}>
      {/* biome-ignore lint/a11y/useMediaCaption: voice memo playback has no caption track */}
      <audio ref={audioRef} src={src} preload="metadata" />
      <button
        type="button"
        className="player-play"
        onClick={toggle}
        disabled={error}
        aria-label={playing ? "Пауза" : "Слушать запись"}
      >
        <Icon name={playing ? "pause" : "play"} size={20} />
      </button>
      <div className="player-track">
        <input
          type="range"
          className="player-range"
          min={0}
          max={duration || 0}
          step={0.1}
          value={current}
          onChange={(event) => seek(Number(event.target.value))}
          aria-label="Позиция воспроизведения"
          style={{ "--progress": `${progress}%` } as CSSProperties}
        />
        <div className="player-times">
          <span>{formatClock(current)}</span>
          <span>{error ? "недоступно" : formatClock(duration)}</span>
        </div>
      </div>
    </div>
  );
}
