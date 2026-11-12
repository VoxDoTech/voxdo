import { useCallback, useEffect, useRef, useState } from "react";
import type { Folder, Note } from "../App";
import { api } from "../lib/api";

interface Props {
  onOpen: (note: Note) => void;
}

const PAGE_SIZE = 50;

function formatDate(iso: string | Date): string {
  const d = new Date(iso);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  return sameDay
    ? d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
}

export function NotesScreen({ onOpen }: Props) {
  const [notes, setNotes] = useState<Note[]>([]);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [folderFilter, setFolderFilter] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [showNew, setShowNew] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newContent, setNewContent] = useState("");
  const [newFolderId, setNewFolderId] = useState("");
  const [showFolders, setShowFolders] = useState(false);
  const [folderName, setFolderName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  // Monotonic request id — responses from superseded filter/search
  // combinations are dropped instead of overwriting newer results.
  const requestSeq = useRef(0);

  const load = useCallback(
    async (offset = 0) => {
      const seq = ++requestSeq.current;
      const [noteList, folderList] = await Promise.all([
        api.note.list({
          folderId: folderFilter ?? undefined,
          q: search.trim() || undefined,
          limit: PAGE_SIZE,
          offset,
        }),
        api.folder.list(),
      ]);
      if (seq !== requestSeq.current) return;
      setNotes((prev) => (offset === 0 ? noteList : [...prev, ...noteList]));
      setHasMore(noteList.length === PAGE_SIZE);
      setFolders(folderList);
    },
    [folderFilter, search],
  );

  useEffect(() => {
    setLoadingMore(false);
    void load().catch((e) =>
      setError(e instanceof Error ? e.message : "Ошибка загрузки"),
    );
  }, [load]);

  const createNote = async () => {
    if (!newContent.trim() && !newTitle.trim()) return;
    await api.note.create({
      title: newTitle.trim() || undefined,
      content: newContent.trim(),
      folderId: newFolderId || undefined,
    });
    setShowNew(false);
    setNewTitle("");
    setNewContent("");
    setNewFolderId("");
    await load();
  };

  const createFolder = async () => {
    if (!folderName.trim()) return;
    await api.folder.create({ name: folderName.trim() });
    setFolderName("");
    await load();
  };

  const folderNameOf = (id: string | null) =>
    id ? (folders.find((f) => f.id === id)?.name ?? null) : null;

  return (
    <div className="screen">
      <div className="toolbar">
        <input
          className="search"
          placeholder="Поиск по заметкам…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button
          type="button"
          className="icon-btn"
          onClick={() => setShowFolders((v) => !v)}
        >
          Папки
        </button>
        <button
          type="button"
          className="icon-btn"
          onClick={() => setShowNew((v) => !v)}
        >
          + Заметка
        </button>
      </div>

      {showFolders && (
        <div className="panel">
          <div className="chips">
            <button
              type="button"
              className={folderFilter === null ? "chip active" : "chip"}
              onClick={() => setFolderFilter(null)}
            >
              Все
            </button>
            {folders.map((f) => (
              <button
                type="button"
                key={f.id}
                className={folderFilter === f.id ? "chip active" : "chip"}
                onClick={() => setFolderFilter(f.id)}
              >
                {f.name}
              </button>
            ))}
          </div>
          <div className="row">
            <input
              placeholder="Новая папка…"
              value={folderName}
              onChange={(e) => setFolderName(e.target.value)}
            />
            <button
              type="button"
              className="small"
              onClick={() => void createFolder()}
            >
              Создать
            </button>
          </div>
        </div>
      )}

      {showNew && (
        <div className="panel">
          <input
            placeholder="Заголовок (необязательно)"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
          />
          <textarea
            placeholder="Текст заметки…"
            rows={4}
            value={newContent}
            onChange={(e) => setNewContent(e.target.value)}
          />
          {folders.length > 0 && (
            <select
              value={newFolderId}
              onChange={(e) => setNewFolderId(e.target.value)}
            >
              <option value="">Без папки</option>
              {folders.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>
          )}
          <button
            type="button"
            className="primary"
            onClick={() => void createNote()}
          >
            Сохранить
          </button>
        </div>
      )}

      {error && <p className="error">{error}</p>}

      <ul className="note-list">
        {notes.map((note) => (
          <li key={note.id}>
            <button
              type="button"
              className="note-card"
              onClick={() => onOpen(note)}
            >
              <div className="note-head">
                <span className="note-title">
                  {note.kind === "voice" ? "🎙 " : ""}
                  {note.title ?? note.content.slice(0, 60) ?? "Без названия"}
                </span>
                <span className="note-date">{formatDate(note.createdAt)}</span>
              </div>
              {note.title && (
                <p className="note-preview">
                  {note.status === "processing"
                    ? "Транскрибируется…"
                    : note.content.slice(0, 120)}
                </p>
              )}
              <div className="note-meta">
                {note.status === "processing" && (
                  <span className="badge">…</span>
                )}
                {note.status === "error" && (
                  <span className="badge error">ошибка</span>
                )}
                {folderNameOf(note.folderId) && (
                  <span className="badge folder">
                    {folderNameOf(note.folderId)}
                  </span>
                )}
                {note.kind === "voice" && (
                  <span className="badge voice">voice</span>
                )}
              </div>
            </button>
          </li>
        ))}
        {notes.length === 0 && !error && (
          <li className="empty">
            Пока пусто. Нажми «Записать» и надиктуй заметку.
          </li>
        )}
      </ul>

      {hasMore && (
        <button
          type="button"
          className="ghost"
          disabled={loadingMore}
          onClick={() => {
            setLoadingMore(true);
            void load(notes.length)
              .catch((e) =>
                setError(e instanceof Error ? e.message : "Ошибка загрузки"),
              )
              .finally(() => setLoadingMore(false));
          }}
        >
          {loadingMore ? "Загрузка…" : "Загрузить ещё"}
        </button>
      )}
    </div>
  );
}
