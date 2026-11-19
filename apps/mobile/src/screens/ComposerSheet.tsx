import { useEffect, useRef, useState } from "react";

import type { Folder, Note } from "../App";
import { Icon } from "../components/Icon";
import { Sheet } from "../components/Sheet";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";

interface Props {
  open: boolean;
  folders: Folder[];
  initialFolderId: string | null;
  onClose: () => void;
  onCreated: (note: Note) => void;
}

export function ComposerSheet({
  open,
  folders,
  initialFolderId,
  onClose,
  onCreated,
}: Props) {
  const toast = useToast();
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [folderId, setFolderId] = useState<string | null>(initialFolderId);
  const [busy, setBusy] = useState(false);
  const bodyRef = useRef<HTMLTextAreaElement | null>(null);
  const generationRef = useRef(0);

  useEffect(() => {
    if (!open) return;
    generationRef.current += 1;
    setTitle("");
    setContent("");
    setFolderId(initialFolderId);
    setBusy(false);
    const timer = setTimeout(() => bodyRef.current?.focus(), 260);
    return () => clearTimeout(timer);
  }, [open, initialFolderId]);

  const create = async () => {
    if (busy) return;
    if (!title.trim() && !content.trim()) return;
    const generation = generationRef.current;
    setBusy(true);
    try {
      const note = await api.note.create({
        title: title.trim() || undefined,
        content: content.trim(),
        folderId: folderId ?? undefined,
      });
      // Always report the created note; only the run that still owns the
      // sheet may close it, show a toast or clear its busy state.
      onCreated(note);
      if (generationRef.current !== generation) return;
      toast.show("Заметка создана", "success");
      onClose();
    } catch (error) {
      if (generationRef.current !== generation) return;
      toast.show(
        error instanceof Error ? error.message : "Не удалось создать заметку",
        "error",
      );
    } finally {
      if (generationRef.current === generation) setBusy(false);
    }
  };

  const canSave = Boolean(title.trim() || content.trim());

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Новая заметка"
      description="Мысль, список, план — всё в одном месте"
    >
      <input
        className="sheet-title-input"
        placeholder="Заголовок"
        value={title}
        onChange={(event) => setTitle(event.target.value)}
      />
      <textarea
        ref={bodyRef}
        className="sheet-editor"
        placeholder="Начните печатать…"
        rows={6}
        value={content}
        onChange={(event) => setContent(event.target.value)}
      />

      {folders.length > 0 && (
        <div className="chips chips-wrap">
          <button
            type="button"
            className={folderId === null ? "chip active" : "chip"}
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
              onClick={() => setFolderId(folder.id)}
            >
              <Icon name="folder" size={14} />
              {folder.name}
            </button>
          ))}
        </div>
      )}

      <div className="sheet-actions">
        <button type="button" className="btn btn-ghost" onClick={onClose}>
          Отмена
        </button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={busy || !canSave}
          onClick={() => void create()}
        >
          {busy ? "Сохраняем…" : "Сохранить"}
        </button>
      </div>
    </Sheet>
  );
}
