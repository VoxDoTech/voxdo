import { useEffect, useRef, useState } from "react";
import type { Note } from "../App";
import { api } from "../lib/api";

interface Props {
  note: Note;
  onBack: () => void;
  onDeleted: () => void;
}

export function NoteDetailScreen({ note, onBack, onDeleted }: Props) {
  const [content, setContent] = useState(note.content);
  const [title, setTitle] = useState(note.title ?? "");
  const [status, setStatus] = useState(note.status);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Fields the user has touched must not be overwritten by polling.
  const contentDirty = useRef(false);
  const titleDirty = useRef(false);

  // Poll while the transcription is running.
  useEffect(() => {
    if (note.status !== "processing") return;
    const timer = setInterval(async () => {
      try {
        const fresh = await api.note.byId({ id: note.id });
        setStatus(fresh.status);
        if (fresh.status !== "processing") {
          if (!contentDirty.current) setContent(fresh.content);
          if (!titleDirty.current) setTitle(fresh.title ?? "");
          clearInterval(timer);
        }
      } catch {
        clearInterval(timer);
      }
    }, 2500);
    return () => clearInterval(timer);
  }, [note.id, note.status]);

  useEffect(() => {
    if (note.kind !== "voice") return;
    api.note
      .audioUrl({ id: note.id })
      .then((r) => setAudioUrl(r.url))
      .catch(() => undefined);
  }, [note.id, note.kind]);

  const save = async () => {
    // Serialize saves: a second tap while a request is in flight could
    // otherwise land an older payload after a newer one.
    if (saving) return;
    setSaving(true);
    setError(null);
    try {
      await api.note.update({
        id: note.id,
        title: title || null,
        content,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось сохранить");
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    try {
      await api.note.delete({ id: note.id });
      onDeleted();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось удалить");
    }
  };

  return (
    <div className="screen">
      <div className="toolbar">
        <button type="button" className="icon-btn" onClick={onBack}>
          ← Назад
        </button>
        <button
          type="button"
          className="icon-btn danger"
          onClick={() => void remove()}
        >
          Удалить
        </button>
      </div>

      <input
        className="title-input"
        placeholder="Заголовок"
        value={title}
        onChange={(e) => {
          titleDirty.current = true;
          setTitle(e.target.value);
        }}
      />

      {status === "processing" && (
        <p className="badge processing">Транскрибируется…</p>
      )}
      {status === "error" && (
        <p className="badge error">
          Ошибка транскрипции{note.errorMessage ? `: ${note.errorMessage}` : ""}
        </p>
      )}
      {error && <p className="error">{error}</p>}

      {audioUrl && (
        // biome-ignore lint/a11y/useMediaCaption: voice memo playback has no caption track
        <audio controls src={audioUrl} className="player" />
      )}

      <textarea
        className="editor"
        value={content}
        onChange={(e) => {
          contentDirty.current = true;
          setContent(e.target.value);
        }}
        placeholder={
          status === "processing" ? "Ждите транскрипцию…" : "Текст заметки…"
        }
      />

      <button
        type="button"
        className="primary"
        disabled={saving}
        onClick={() => void save()}
      >
        {saving ? "Сохранение…" : saved ? "Сохранено ✓" : "Сохранить"}
      </button>
    </div>
  );
}
