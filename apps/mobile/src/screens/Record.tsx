import { useEffect, useRef, useState } from "react";

import { api } from "../lib/api";
import { VoiceRecorder } from "../lib/recorder";

interface Props {
  onSaved: () => void;
}

type Phase = "idle" | "recording" | "uploading" | "done" | "error";

export function RecordScreen({ onSaved }: Props) {
  const recorderRef = useRef<VoiceRecorder | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (phase !== "recording") return;
    const timer = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, [phase]);

  const start = async () => {
    setError(null);
    try {
      const recorder = new VoiceRecorder();
      await recorder.start();
      recorderRef.current = recorder;
      setElapsed(0);
      setPhase("recording");
    } catch {
      setError("Нет доступа к микрофону");
      setPhase("error");
    }
  };

  const stopAndSave = async () => {
    const recorder = recorderRef.current;
    if (!recorder) return;
    setPhase("uploading");
    try {
      const audio = await recorder.stop();
      recorderRef.current = null;
      await api.note.createVoice({
        audioBase64: audio.base64,
        mimeType: audio.mimeType,
        durationSec: audio.durationSec,
      });
      setPhase("done");
      setTimeout(onSaved, 600);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось сохранить");
      setPhase("error");
    }
  };

  const cancel = () => {
    recorderRef.current?.cancel();
    recorderRef.current = null;
    setPhase("idle");
  };

  const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");

  return (
    <div className="screen record-screen">
      <p className="hint">
        Нажми кнопку и говори — до 2 минут. Приложение расшифрует и сохранит
        заметку.
      </p>

      {phase === "recording" || phase === "uploading" ? (
        <div className="rec-time">
          {phase === "recording" ? "●" : "…"} {mm}:{ss}
        </div>
      ) : null}

      {error && <p className="error">{error}</p>}
      {phase === "done" && <p className="ok">Сохранено — транскрибируется…</p>}

      <div className="rec-controls">
        {phase === "idle" || phase === "error" ? (
          <button
            type="button"
            className="rec-btn"
            onClick={() => void start()}
          >
            ●
          </button>
        ) : phase === "recording" ? (
          <>
            <button type="button" className="rec-btn stop" onClick={cancel}>
              ✕
            </button>
            <button
              type="button"
              className="rec-btn"
              onClick={() => void stopAndSave()}
            >
              ■
            </button>
          </>
        ) : (
          <div className="spinner" />
        )}
      </div>

      {phase === "recording" && (
        <button type="button" className="ghost" onClick={cancel}>
          Отмена
        </button>
      )}
    </div>
  );
}
