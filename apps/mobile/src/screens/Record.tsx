import { useEffect, useRef, useState } from "react";

import { api } from "../lib/api";
import { type RecordedAudio, VoiceRecorder } from "../lib/recorder";

interface Props {
  onSaved: () => void;
}

type Phase = "idle" | "starting" | "recording" | "uploading" | "done" | "error";

export function RecordScreen({ onSaved }: Props) {
  const recorderRef = useRef<VoiceRecorder | null>(null);
  const mountedRef = useRef(true);
  const [phase, setPhase] = useState<Phase>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  // Kept after stop() so a failed upload can be retried without re-recording.
  const [pendingAudio, setPendingAudio] = useState<RecordedAudio | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      // Stop the mic when leaving the tab — including a start() that is
      // still waiting for permission (VoiceRecorder.cancel covers both).
      recorderRef.current?.cancel();
      recorderRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (phase !== "recording") return;
    const timer = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, [phase]);

  const start = async () => {
    // recorderRef is set synchronously — a second tap can't start a
    // parallel recorder while the first is still acquiring the mic.
    if (recorderRef.current) return;
    setError(null);
    const recorder = new VoiceRecorder();
    recorderRef.current = recorder;
    setPhase("starting");
    try {
      await recorder.start();
      if (!mountedRef.current) {
        recorder.cancel();
        recorderRef.current = null;
        return;
      }
      setElapsed(0);
      setPhase("recording");
    } catch {
      recorderRef.current = null;
      if (mountedRef.current) {
        setError("Нет доступа к микрофону");
        setPhase("error");
      }
    }
  };

  const upload = async (audio: RecordedAudio) => {
    setPhase("uploading");
    setError(null);
    try {
      await api.note.createVoice({
        audioBase64: audio.base64,
        mimeType: audio.mimeType,
        durationSec: audio.durationSec,
      });
      setPendingAudio(null);
      setPhase("done");
      setTimeout(onSaved, 600);
    } catch (e) {
      setPendingAudio(audio);
      setError(e instanceof Error ? e.message : "Не удалось сохранить");
      setPhase("error");
    }
  };

  const stopAndSave = async () => {
    const recorder = recorderRef.current;
    if (!recorder) return;
    try {
      const audio = await recorder.stop();
      recorderRef.current = null;
      await upload(audio);
    } catch (e) {
      recorder.cancel();
      recorderRef.current = null;
      setError(e instanceof Error ? e.message : "Не удалось сохранить");
      setPhase("error");
    }
  };

  const cancel = () => {
    recorderRef.current?.cancel();
    recorderRef.current = null;
    setPhase("idle");
  };

  const discardPending = () => {
    setPendingAudio(null);
    setError(null);
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

      {pendingAudio && phase === "error" && (
        <div className="row">
          <button
            type="button"
            className="primary"
            onClick={() => void upload(pendingAudio)}
          >
            Повторить отправку
          </button>
          <button type="button" className="ghost" onClick={discardPending}>
            Удалить запись
          </button>
        </div>
      )}
    </div>
  );
}
