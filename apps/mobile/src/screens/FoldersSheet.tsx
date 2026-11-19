import { useEffect, useState } from "react";

import type { Folder } from "../App";
import { Icon } from "../components/Icon";
import { Sheet } from "../components/Sheet";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";

interface Props {
  open: boolean;
  folders: Folder[];
  onClose: () => void;
  onChanged: () => void;
}

export function FoldersSheet({ open, folders, onClose, onChanged }: Props) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) {
      setName("");
      setEditingId(null);
      setConfirmId(null);
    }
  }, [open]);

  const create = async () => {
    const trimmed = name.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    try {
      await api.folder.create({ name: trimmed });
      setName("");
      onChanged();
      toast.show("Папка создана", "success");
    } catch (error) {
      toast.show(
        error instanceof Error ? error.message : "Не удалось создать папку",
        "error",
      );
    } finally {
      setBusy(false);
    }
  };

  const rename = async (id: string) => {
    const trimmed = editingName.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    try {
      await api.folder.update({ id, name: trimmed });
      setEditingId(null);
      onChanged();
      toast.show("Папка переименована", "success");
    } catch (error) {
      toast.show(error instanceof Error ? error.message : "Ошибка", "error");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    if (confirmId !== id) {
      setConfirmId(id);
      return;
    }
    setBusy(true);
    try {
      await api.folder.delete({ id });
      setConfirmId(null);
      onChanged();
      toast.show("Папка удалена, заметки сохранены", "success");
    } catch (error) {
      toast.show(error instanceof Error ? error.message : "Ошибка", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Папки"
      description="Группируйте заметки по темам и проектам"
    >
      <div className="field-row">
        <div className="input-with-icon">
          <Icon name="folderPlus" size={18} />
          <input
            placeholder="Название папки"
            value={name}
            onChange={(event) => setName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void create();
            }}
          />
        </div>
        <button
          type="button"
          className="btn btn-primary btn-compact"
          disabled={busy || !name.trim()}
          onClick={() => void create()}
        >
          Создать
        </button>
      </div>

      {folders.length === 0 ? (
        <p className="sheet-empty">
          Пока нет папок. Например: «Работа», «Идеи», «Здоровье».
        </p>
      ) : (
        <ul className="folder-list">
          {folders.map((folder) => (
            <li key={folder.id} className="folder-row">
              <span className="folder-icon">
                <Icon name="folder" size={18} />
              </span>
              {editingId === folder.id ? (
                <input
                  className="folder-rename"
                  value={editingName}
                  // biome-ignore lint/a11y/noAutofocus: appears only after "rename" is tapped
                  autoFocus
                  onChange={(event) => setEditingName(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") void rename(folder.id);
                    if (event.key === "Escape") setEditingId(null);
                  }}
                />
              ) : (
                <span className="folder-name">{folder.name}</span>
              )}
              <div className="folder-actions">
                {editingId === folder.id ? (
                  <button
                    type="button"
                    className="btn-icon accent"
                    aria-label="Сохранить название"
                    onClick={() => void rename(folder.id)}
                  >
                    <Icon name="check" size={17} />
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn-icon"
                    aria-label="Переименовать папку"
                    onClick={() => {
                      setEditingId(folder.id);
                      setEditingName(folder.name);
                      setConfirmId(null);
                    }}
                  >
                    <Icon name="edit" size={16} />
                  </button>
                )}
                <button
                  type="button"
                  className={
                    confirmId === folder.id
                      ? "btn-icon danger armed"
                      : "btn-icon danger"
                  }
                  aria-label={
                    confirmId === folder.id
                      ? "Подтвердить удаление"
                      : "Удалить папку"
                  }
                  onClick={() => void remove(folder.id)}
                >
                  <Icon
                    name={confirmId === folder.id ? "check" : "trash"}
                    size={16}
                  />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {confirmId && (
        <p className="sheet-note">
          Нажмите галочку ещё раз — заметки останутся, но выйдут из папки.
        </p>
      )}
    </Sheet>
  );
}
