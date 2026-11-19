import {
  type CSSProperties,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import type { Folder, Note } from "../App";
import { Icon } from "../components/Icon";
import { LiveWave } from "../components/LiveWave";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";
import { formatClock } from "../lib/format";
import { type RecordedAudio, VoiceRecorder } from "../lib/recorder";

const MAX_SECONDS = 120;
const MAX_MS = MAX_SECONDS * 1000;

type Phase =
  | "idle"
  | "starting"
  | "recording"
  | "paused"
  | "uploading"
  | "done"
  | "error";

interface Props {
  onSaved: (note: Note) => void;
}

export function RecordScreen({ onSaved }: Props) {
  const toast = useToast();
  const recorderRef = useRef<VoiceRecorder | null>(null);
  const mountedRef = useRef(true);
  const uploadingRef = useRef(false);
  const autoStoppedRef = useRef(false);
  const stopRef = useRef<() => void>(() => undefined);
  const [phase, setPhase] = useState<Phase>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [pendingAudio, setPendingAudio] = useState<RecordedAudio | null>(null);
  const [lastNote, setLastNote] = useState<Note | null>(null);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [folderId, setFolderId] = useState<string | null>(null);

  useEffect(() => {
    void api.folder
      .list()
      .then(setFolders)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      recorderRef.current?.cancel();
      recorderRef.current = null;
    };
  }, []);

  const upload = useCallback(
    async (audio: RecordedAudio) => {
      setPhase("uploading");
      setError(null);
      try {
        const note = await api.note.createVoice({
          audioBase64: audio.base64,
          mimeType: audio.mimeType,
          durationSec: audio.durationSec,
          folderId: folderId ?? undefined,
        });
        setPendingAudio(null);
        setLastNote(note);
        setPhase("done");
        navigator.vibrate?.([18, 40, 18]);
        toast.show("Запись сохранена — расшифровываем", "success");
      } catch (cause) {
        setPendingAudio(audio);
        setError(
          cause instanceof Error
            ? cause.message
            : "Не удалось сохранить запись",
        );
        setPhase("error");
      }
    },
    [folderId, toast],
  );

  const stopAndSave = useCallback(async () => {
    const recorder = recorderRef.current;
    if (!recorder || uploadingRef.current) return;
    uploadingRef.current = true;
    try {
      const audio = await recorder.stop();
      recorderRef.current = null;
      await upload(audio);
    } catch (cause) {
      recorder.cancel();
      recorderRef.current = null;
      setError(
        cause instanceof Error ? cause.message : "Не удалось сохранить запись",
      );
      setPhase("error");
    } finally {
      uploadingRef.current = false;
    }
  }, [upload]);

  const start = async () => {
    if (recorderRef.current) return;
    setError(null);
    setLastNote(null);
    setPendingAudio(null);
    setElapsed(0);
    setPhase("starting");
    autoStoppedRef.current = false;
    const recorder = new VoiceRecorder();
    recorderRef.current = recorder;
    try {
      await recorder.start();
      if (!mountedRef.current) {
        recorder.cancel();
        recorderRef.current = null;
        return;
      }
      setPhase("recording");
      navigator.vibrate?.(12);
    } catch {
      recorderRef.current = null;
      if (mountedRef.current) {
        setError(
          "Нет доступа к микрофону. Разрешите запись в настройках приложения.",
        );
        setPhase("error");
      }
    }
  };

  const togglePause = () => {
    const recorder = recorderRef.current;
    if (!recorder) return;
    if (recorder.isPaused) {
      recorder.resume();
      setPhase("recording");
    } else {
      recorder.pause();
      setElapsed(recorder.elapsedMs());
      setPhase("paused");
    }
    navigator.vibrate?.(10);
  };

  const cancel = () => {
    recorderRef.current?.cancel();
    recorderRef.current = null;
    setPendingAudio(null);
    setError(null);
    setLastNote(null);
    setElapsed(0);
    setPhase("idle");
  };

  const clearFinished = () => {
    setError(null);
    setPendingAudio(null);
    setLastNote(null);
    setElapsed(0);
    setPhase("idle");
  };

  // Auto-stop at the 2-minute limit.
  useEffect(() => {
    stopRef.current = () => {
      void stopAndSave();
    };
  });

  useEffect(() => {
    if (phase !== "recording" && phase !== "paused") return;
    const timer = setInterval(() => {
      const recorder = recorderRef.current;
      if (!recorder) return;
      const ms = recorder.elapsedMs();
      setElapsed(ms);
      if (ms >= MAX_MS && !autoStoppedRef.current) {
        autoStoppedRef.current = true;
        navigator.vibrate?.([20, 60, 20]);
        stopRef.current();
      }
    }, 200);
    return () => clearInterval(timer);
  }, [phase]);

  const level = useCallback(() => recorderRef.current?.getLevel() ?? 0, []);

  const seconds = Math.floor(elapsed / 1000);
  const progress = Math.min(100, (elapsed / MAX_MS) * 100);
  const isLive = phase === "recording" || phase === "paused";
  const elapsedLabel = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(
    seconds % 60,
  ).padStart(2, "0")}`;

  const statusText: Record<Phase, string> = {
    idle: "Нажмите кнопку и говорите — расшифруем автоматически",
    starting: "Включаем микрофон…",
    recording: "Слушаем вас. Нажмите квадрат, чтобы остановить",
    paused: "Пауза — можно продолжить в любой момент",
    uploading: "Загружаем запись и отправляем на расшифровку…",
    done: "Готово! Заметка уже в списке",
    error: error ?? "Что-то пошло не так",
  };

  const handleMain = () => {
    const recorder = recorderRef.current;
    if (recorder) {
      void stopAndSave();
    } else {
      void start();
    }
  };

  return (
    <div className="screen record-screen">
      <div className="record-inner">
        <div className="screen-head compact">
          <div>
            <p className="eyebrow">Диктофон</p>
            <h1>Записать</h1>
          </div>
          <span className="limit-pill">
            <Icon name="clock" size={13} />
            до 2 мин
          </span>
        </div>

        {folders.length > 0 && (
          <div className="chips chips-center">
            <button
              type="button"
              className={folderId === null ? "chip active" : "chip"}
              disabled={isLive || phase === "uploading"}
              onClick={() => setFolderId(null)}
            >
              <Icon name="file" size={14} />
              Без папки
            </button>
            {folders.map((folder) => (
              <button
                type="button"
                key={folder.id}
                className={folderId === folder.id ? "chip active" : "chip"}
                disabled={isLive || phase === "uploading"}
                onClick={() => setFolderId(folder.id)}
              >
                <Icon name="folder" size={14} />
                {folder.name}
              </button>
            ))}
          </div>
        )}

        <div className="record-stage">
          <div
            className={`mic-wrap phase-${phase}`}
            style={{ "--progress": `${progress}%` } as CSSProperties}
          >
            <span className="mic-glow" />
            {isLive && (
              <>
                <span className="mic-ripple" />
                <span className="mic-ripple delay" />
              </>
            )}
            <span className="mic-progress" />
            <button
              type="button"
              className={`mic-btn${isLive ? " live" : ""}${phase === "uploading" ? " busy" : ""}${phase === "done" ? " done" : ""}`}
              onClick={handleMain}
              disabled={
                phase === "starting" ||
                phase === "uploading" ||
                (phase === "error" && Boolean(pendingAudio))
              }
              aria-label={
                isLive ? "Остановить запись" : "Начать запись голосовой заметки"
              }
            >
              {phase === "starting" || phase === "uploading" ? (
                <span className="spinner-ring light" />
              ) : phase === "done" ? (
                <Icon name="check" size={44} strokeWidth={2.4} />
              ) : isLive ? (
                <Icon name="stop" size={40} strokeWidth={1.6} />
              ) : (
                <Icon name="mic" size={44} strokeWidth={1.7} />
              )}
            </button>
          </div>

          <div className={`record-timer${isLive ? " live" : ""}`}>
            {elapsedLabel}
            <span>/ {formatClock(MAX_SECONDS)}</span>
          </div>

          <p
            className={`record-status${phase === "error" ? " error" : ""}`}
            aria-live="polite"
          >
            {statusText[phase]}
          </p>
        </div>

        <div className="record-wave">
          <LiveWave getLevel={level} active={phase === "recording"} />
        </div>

        <div className="record-actions">
          {isLive && (
            <>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={togglePause}
              >
                <Icon name={phase === "paused" ? "play" : "pause"} size={16} />
                {phase === "paused" ? "Продолжить" : "Пауза"}
              </button>
              <button
                type="button"
                className="btn btn-ghost danger-text"
                onClick={cancel}
              >
                <Icon name="trash" size={16} />
                Отменить
              </button>
            </>
          )}

          {phase === "done" && lastNote && (
            <>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => onSaved(lastNote)}
              >
                Открыть заметку
                <Icon name="arrowRight" size={17} />
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={clearFinished}
              >
                Ещё запись
              </button>
            </>
          )}

          {phase === "error" && pendingAudio && (
            <>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void upload(pendingAudio)}
              >
                Повторить отправку
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={clearFinished}
              >
                Удалить запись
              </button>
            </>
          )}
        </div>

        <p className="record-footnote">
          {folderId
            ? "Запись попадёт в выбранную папку"
            : "Можно выбрать папку перед началом записи"}
        </p>
      </div>
    </div>
  );
}
