import { useCallback, useEffect, useRef, useState } from "react";

import type { Folder, Note } from "../App";
import { AudioPlayer } from "../components/AudioPlayer";
import { Icon } from "../components/Icon";
import { Sheet } from "../components/Sheet";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";
import { formatClock, formatFull, wordCount } from "../lib/format";

type SaveState = "idle" | "saving" | "saved" | "error";

interface Props {
  note: Note;
  onBack: () => void;
  onDeleted: () => void;
}

export function NoteDetailScreen({ note, onBack, onDeleted }: Props) {
  const toast = useToast();
  const [title, setTitle] = useState(note.title ?? "");
  const [content, setContent] = useState(note.content);
  const [status, setStatus] = useState(note.status);
  const [errorMessage, setErrorMessage] = useState(note.errorMessage);
  const [folderId, setFolderId] = useState(note.folderId);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [editSeq, setEditSeq] = useState(0);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [pollError, setPollError] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const titleTouched = useRef(false);
  const savingRef = useRef(false);
  const pendingRef = useRef(false);
  const waitersRef = useRef<((ok: boolean) => void)[]>([]);
  const latest = useRef({ title, content, folderId });
  latest.current = { title, content, folderId };

  useEffect(() => {
    void api.folder
      .list()
      .then(setFolders)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (note.kind !== "voice") return;
    api.note
      .audioUrl({ id: note.id })
      .then((result) => setAudioUrl(result.url))
      .catch(() => undefined);
  }, [note.id, note.kind]);

  // Poll while transcription runs, then fill in the transcript.
  useEffect(() => {
    if (status !== "processing") return;
    let active = true;
    const tick = async () => {
      try {
        const fresh = await api.note.byId({ id: note.id });
        if (!active) return;
        setPollError(false);
        setStatus(fresh.status);
        setErrorMessage(fresh.errorMessage);
        if (fresh.status !== "processing") {
          setContent(fresh.content);
          if (!titleTouched.current) setTitle(fresh.title ?? "");
          toast.show(
            fresh.status === "ready"
              ? "Транскрипция готова"
              : "Не удалось расшифровать запись",
            fresh.status === "ready" ? "success" : "error",
          );
        }
      } catch {
        // A failed read says nothing about the transcription job: keep the
        // last server-reported status and keep polling.
        if (active) setPollError(true);
      }
    };
    const timer = setInterval(() => void tick(), 2500);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [note.id, status, toast]);

  // Persist the latest edits. While a request is in flight, additional calls
  // mark the queue dirty instead of racing; the running loop then saves the
  // newest snapshot, and every caller awaits the same drained queue.
  const flush = useCallback(async (): Promise<boolean> => {
    if (savingRef.current) return true;
    savingRef.current = true;
    let ok = true;
    try {
      while (pendingRef.current) {
        pendingRef.current = false;
        const payload: {
          title: string | null;
          content?: string;
          folderId: string | null;
        } = {
          title: latest.current.title.trim() || null,
          folderId: latest.current.folderId,
        };
        // While transcription runs, don't send the stale local content — it
        // would clobber the transcript the worker is about to write.
        if (status !== "processing") payload.content = latest.current.content;
        setSaveState("saving");
        try {
          await api.note.update({ id: note.id, ...payload });
        } catch (cause) {
          ok = false;
          setSaveState("error");
          toast.show(
            cause instanceof Error ? cause.message : "Не удалось сохранить",
            "error",
          );
          break;
        }
        const now = latest.current;
        const unchanged =
          (now.title.trim() || null) === payload.title &&
          (payload.content === undefined || now.content === payload.content) &&
          now.folderId === payload.folderId;
        if (unchanged) {
          setDirty(false);
          setSaveState("saved");
        } else {
          // Newer edits arrived while the request ran — save them next.
          pendingRef.current = true;
        }
      }
    } finally {
      savingRef.current = false;
      const waiters = waitersRef.current;
      waitersRef.current = [];
      for (const resolve of waiters) resolve(ok);
    }
    return ok;
  }, [note.id, status, toast]);

  const save = useCallback((): Promise<boolean> => {
    pendingRef.current = true;
    const result = new Promise<boolean>((resolve) => {
      waitersRef.current.push(resolve);
    });
    void flush();
    return result;
  }, [flush]);

  // Debounced autosave; the explicit button stays as a fallback. `editSeq`
  // re-arms the timer even when `dirty` is already true.
  // biome-ignore lint/correctness/useExhaustiveDependencies: editSeq is a deliberate debounce trigger
  useEffect(() => {
    if (!dirty) return;
    const timer = setTimeout(() => void save(), 1100);
    return () => clearTimeout(timer);
  }, [dirty, editSeq, save]);

  const markDirty = () => {
    setDirty(true);
    setEditSeq((seq) => seq + 1);
    setSaveState((current) => (current === "saving" ? current : "idle"));
  };

  const handleBack = async () => {
    if (dirty) {
      const saved = await save();
      if (!saved) return;
    }
    onBack();
  };

  const copy = async () => {
    const text = [title.trim(), content.trim()].filter(Boolean).join("\n\n");
    try {
      await navigator.clipboard.writeText(text || "Пустая заметка");
      toast.show("Скопировано в буфер", "success");
    } catch {
      toast.show("Не удалось скопировать", "error");
    }
  };

  const share = async () => {
    const text = [title.trim(), content.trim()].filter(Boolean).join("\n\n");
    if (navigator.share) {
      try {
        await navigator.share({
          title: title.trim() || "Заметка VoxDo",
          text: text || "Пустая заметка",
        });
      } catch (cause) {
        if (cause instanceof DOMException && cause.name === "AbortError")
          return;
        toast.show("Не удалось поделиться", "error");
      }
      return;
    }
    await copy();
  };

  const remove = async () => {
    if (deleting) return;
    setDeleting(true);
    try {
      await api.note.delete({ id: note.id });
      toast.show("Заметка удалена", "success");
      onDeleted();
    } catch (cause) {
      toast.show(
        cause instanceof Error ? cause.message : "Не удалось удалить",
        "error",
      );
      setDeleting(false);
      setConfirmOpen(false);
    }
  };

  const words = wordCount(content);
  const folderName =
    folders.find((folder) => folder.id === folderId)?.name ?? null;

  const saveLabel =
    saveState === "saving"
      ? "Сохраняем…"
      : saveState === "error"
        ? "Не удалось сохранить"
        : dirty
          ? "Есть несохранённые изменения"
          : saveState === "saved"
            ? "Все изменения сохранены"
            : "Изменения сохраняются автоматически";

  return (
    <div className="detail">
      <header className="detail-bar">
        <button
          type="button"
          className="btn-icon"
          onClick={() => void handleBack()}
          aria-label="Назад к списку"
        >
          <Icon name="chevronLeft" size={22} />
        </button>
        <div className="detail-bar-title">
          <span>{note.kind === "voice" ? "Голосовая" : "Текстовая"}</span>
          <span className="detail-bar-sub">{formatFull(note.createdAt)}</span>
        </div>
        <div className="detail-actions">
          <button
            type="button"
            className="btn-icon"
            onClick={() => void copy()}
            aria-label="Скопировать текст"
          >
            <Icon name="copy" size={17} />
          </button>
          <button
            type="button"
            className="btn-icon"
            onClick={() => void share()}
            aria-label="Поделиться заметкой"
          >
            <Icon name="share" size={17} />
          </button>
          <button
            type="button"
            className="btn-icon danger"
            onClick={() => setConfirmOpen(true)}
            aria-label="Удалить заметку"
          >
            <Icon name="trash" size={17} />
          </button>
        </div>
      </header>

      <div className="detail-scroll">
        {status === "processing" && (
          <div className="transcribe-banner">
            <span className="spinner-ring small" />
            <div>
              <strong>Расшифровываем запись</strong>
              <span>
                {pollError
                  ? "Нет связи с сервером — продолжаем пытаться"
                  : "Обычно это занимает несколько секунд"}
              </span>
            </div>
          </div>
        )}
        {status === "error" && (
          <div className="inline-error">
            <Icon name="alert" size={18} />
            <span>
              {errorMessage ??
                "Транскрипция не удалась — текст можно ввести вручную."}
            </span>
          </div>
        )}

        <input
          className="detail-title"
          value={title}
          placeholder="Заголовок"
          aria-label="Заголовок заметки"
          onChange={(event) => {
            titleTouched.current = true;
            setTitle(event.target.value);
            markDirty();
          }}
        />

        <div className="detail-meta">
          <span className="badge kind">
            <Icon name={note.kind === "voice" ? "mic" : "file"} size={11} />
            {note.kind === "voice" ? "Голос" : "Текст"}
          </span>
          {note.kind === "voice" && note.audioDurationSec ? (
            <span className="badge voice">
              <Icon name="clock" size={11} />
              {formatClock(note.audioDurationSec)}
            </span>
          ) : null}
          {folderName && (
            <span className="badge folder">
              <Icon name="folder" size={11} />
              {folderName}
            </span>
          )}
        </div>

        {audioUrl && <AudioPlayer src={audioUrl} />}

        <div className="editor-card">
          <div className="editor-head">
            <span>Транскрипт</span>
            <span className="editor-count">
              {words} {words === 1 ? "слово" : words < 5 ? "слова" : "слов"}
            </span>
          </div>
          <textarea
            className="editor"
            value={content}
            disabled={status === "processing"}
            placeholder={
              status === "processing"
                ? "Расшифровываем запись…"
                : "Текст заметки…"
            }
            aria-label="Текст заметки"
            onChange={(event) => {
              setContent(event.target.value);
              markDirty();
            }}
          />
        </div>

        <div className="folder-picker">
          <p className="field-label">Папка</p>
          <div className="chips chips-wrap">
            <button
              type="button"
              className={folderId === null ? "chip active" : "chip"}
              onClick={() => {
                setFolderId(null);
                markDirty();
              }}
            >
              <Icon name="file" size={14} />
              Без папки
            </button>
            {folders.map((folder) => (
              <button
                type="button"
                key={folder.id}
                className={folderId === folder.id ? "chip active" : "chip"}
                onClick={() => {
                  setFolderId(folder.id);
                  markDirty();
                }}
              >
                <Icon name="folder" size={14} />
                {folder.name}
              </button>
            ))}
          </div>
        </div>

        <p className="detail-footnote">Создано {formatFull(note.createdAt)}</p>
      </div>

      <footer className="detail-footer">
        <span className={`save-state ${saveState}`}>{saveLabel}</span>
        <button
          type="button"
          className="btn btn-primary btn-compact"
          disabled={!dirty || saveState === "saving"}
          onClick={() => void save()}
        >
          {saveState === "saving" ? "Сохраняем…" : "Сохранить"}
        </button>
      </footer>

      <Sheet
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="Удалить заметку?"
        description="Это действие нельзя отменить"
      >
        <p className="sheet-text">
          «{title.trim() || "Без названия"}» и её расшифровка будут удалены
          навсегда.
        </p>
        <div className="sheet-actions">
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => setConfirmOpen(false)}
          >
            Оставить
          </button>
          <button
            type="button"
            className="btn btn-danger"
            disabled={deleting}
            onClick={() => void remove()}
          >
            {deleting ? "Удаляем…" : "Удалить"}
          </button>
        </div>
      </Sheet>
    </div>
  );
}
