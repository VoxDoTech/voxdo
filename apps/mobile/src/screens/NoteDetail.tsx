import { useEffect, useState } from "react";
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

  // Poll while the transcription is running.
  useEffect(() => {
    if (note.status !== "processing") return;
    const timer = setInterval(async () => {
      try {
        const fresh = await api.note.byId({ id: note.id });
        setStatus(fresh.status);
        if (fresh.status !== "processing") {
          setContent(fresh.content);
          setTitle(fresh.title ?? "");
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
    await api.note.update({
      id: note.id,
      title: title || null,
      content,
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  const remove = async () => {
    await api.note.delete({ id: note.id });
    onDeleted();
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
        onChange={(e) => setTitle(e.target.value)}
      />

      {status === "processing" && (
        <p className="badge processing">Транскрибируется…</p>
      )}
      {status === "error" && (
        <p className="badge error">
          Ошибка транскрипции{note.errorMessage ? `: ${note.errorMessage}` : ""}
        </p>
      )}

      {audioUrl && (
        // biome-ignore lint/a11y/useMediaCaption: voice memo playback has no caption track
        <audio controls src={audioUrl} className="player" />
      )}

      <textarea
        className="editor"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder={
          status === "processing" ? "Ждите транскрипцию…" : "Текст заметки…"
        }
      />

      <button type="button" className="primary" onClick={() => void save()}>
        {saved ? "Сохранено ✓" : "Сохранить"}
      </button>
    </div>
  );
}
