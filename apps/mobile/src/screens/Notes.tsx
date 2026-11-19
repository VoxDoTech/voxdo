import { useCallback, useEffect, useRef, useState } from "react";

import type { Folder, Note } from "../App";
import { Icon } from "../components/Icon";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";
import {
  dayKey,
  dayLabel,
  formatClock,
  formatRelative,
  noteTitle,
} from "../lib/format";
import { ComposerSheet } from "./ComposerSheet";
import { FoldersSheet } from "./FoldersSheet";

const PAGE_SIZE = 30;

type KindFilter = "all" | "voice" | "text";

interface Props {
  /** Bumped by the shell after a recording / edit / delete. */
  reloadKey: number;
  onOpen: (note: Note) => void;
  onRecord: () => void;
}

export function NotesScreen({ reloadKey, onOpen, onRecord }: Props) {
  const toast = useToast();
  const [notes, setNotes] = useState<Note[]>([]);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [kind, setKind] = useState<KindFilter>("all");
  const [folderId, setFolderId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [composerOpen, setComposerOpen] = useState(false);
  const [foldersOpen, setFoldersOpen] = useState(false);
  const [refreshToken, setRefreshToken] = useState(0);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  // Responses from superseded filter/search combinations are dropped.
  const requestSeq = useRef(0);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(search.trim()), 320);
    return () => clearTimeout(timer);
  }, [search]);

  const loadFolders = useCallback(async () => {
    try {
      const list = await api.folder.list();
      setFolders(list);
      setFolderId((current) =>
        current && !list.some((folder) => folder.id === current)
          ? null
          : current,
      );
    } catch {
      // Folder chips are optional — keep the notes list usable.
    }
  }, []);

  // biome-ignore lint/correctness/useExhaustiveDependencies: reloadKey/refreshToken are deliberate refetch triggers
  useEffect(() => {
    void loadFolders();
  }, [loadFolders, reloadKey, refreshToken]);

  const loadFirst = useCallback(async () => {
    const seq = ++requestSeq.current;
    setLoading(true);
    setError(null);
    try {
      const list = await api.note.list({
        q: debounced || undefined,
        folderId: folderId ?? undefined,
        kind: kind === "all" ? undefined : kind,
        limit: PAGE_SIZE,
        offset: 0,
      });
      if (seq !== requestSeq.current) return;
      setNotes(list);
      setHasMore(list.length === PAGE_SIZE);
    } catch (cause) {
      if (seq !== requestSeq.current) return;
      setError(
        cause instanceof Error ? cause.message : "Не удалось загрузить заметки",
      );
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  }, [debounced, folderId, kind]);

  // biome-ignore lint/correctness/useExhaustiveDependencies: reloadKey/refreshToken are deliberate refetch triggers
  useEffect(() => {
    void loadFirst();
  }, [loadFirst, reloadKey, refreshToken]);

  const loadMore = useCallback(async () => {
    if (loading || loadingMore || !hasMore) return;
    const seq = requestSeq.current;
    setLoadingMore(true);
    try {
      const list = await api.note.list({
        q: debounced || undefined,
        folderId: folderId ?? undefined,
        kind: kind === "all" ? undefined : kind,
        limit: PAGE_SIZE,
        offset: notes.length,
      });
      if (seq !== requestSeq.current) return;
      setNotes((prev) => [...prev, ...list]);
      setHasMore(list.length === PAGE_SIZE);
    } catch (cause) {
      toast.show(
        cause instanceof Error ? cause.message : "Не удалось загрузить ещё",
        "error",
      );
    } finally {
      setLoadingMore(false);
    }
  }, [
    debounced,
    folderId,
    hasMore,
    kind,
    loading,
    loadingMore,
    notes.length,
    toast,
  ]);

  useEffect(() => {
    const target = sentinelRef.current;
    if (!target || !hasMore || loading || loadingMore) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) void loadMore();
      },
      { root: scrollRef.current, rootMargin: "240px" },
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [hasMore, loading, loadMore, loadingMore]);

  // Poll notes that are still transcribing, and announce when they land.
  const processingKey = notes
    .filter((note) => note.status === "processing")
    .map((note) => note.id)
    .join(",");

  useEffect(() => {
    if (!processingKey) return;
    const ids = processingKey.split(",");
    const timer = setInterval(async () => {
      const updates = await Promise.all(
        ids.map((id) => api.note.byId({ id }).catch(() => null)),
      );
      const becameReady = updates.filter(
        (fresh) => fresh?.status === "ready",
      ).length;
      setNotes((prev) =>
        prev.map((note) => {
          const fresh = updates.find((item) => item?.id === note.id);
          if (!fresh) return note;
          return {
            ...note,
            title: fresh.title,
            content: fresh.content,
            status: fresh.status,
            errorMessage: fresh.errorMessage,
          };
        }),
      );
      if (becameReady > 0) {
        toast.show(
          becameReady === 1
            ? "Транскрипция готова"
            : `Готово транскрипций: ${becameReady}`,
          "success",
        );
      }
    }, 4000);
    return () => clearInterval(timer);
  }, [processingKey, toast]);

  const refresh = () => setRefreshToken((value) => value + 1);

  const filtersActive =
    Boolean(debounced) || kind !== "all" || Boolean(folderId);

  const resetFilters = () => {
    setSearch("");
    setDebounced("");
    setKind("all");
    setFolderId(null);
  };

  const folderNameOf = (id: string | null) =>
    id ? (folders.find((folder) => folder.id === id)?.name ?? null) : null;

  const groupMap = new Map<
    string,
    { key: string; label: string; items: Note[] }
  >();
  for (const note of notes) {
    const key = dayKey(note.createdAt);
    const group = groupMap.get(key);
    if (group) {
      group.items.push(note);
    } else {
      groupMap.set(key, {
        key,
        label: dayLabel(note.createdAt),
        items: [note],
      });
    }
  }
  const groups = [...groupMap.values()];

  return (
    <div className="screen">
      <div className="screen-scroll" ref={scrollRef}>
        <div className="screen-head">
          <div>
            <p className="eyebrow">Ваш второй мозг</p>
            <h1>
              Заметки
              {!loading && notes.length > 0 && (
                <span className="count-pill">
                  {notes.length}
                  {hasMore ? "+" : ""}
                </span>
              )}
            </h1>
          </div>
          <div className="head-actions">
            <button
              type="button"
              className="btn-icon"
              onClick={refresh}
              aria-label="Обновить список"
            >
              <Icon name="refresh" size={18} />
            </button>
            <button
              type="button"
              className="btn-icon accent"
              onClick={() => setComposerOpen(true)}
              aria-label="Новая текстовая заметка"
            >
              <Icon name="plus" size={20} />
            </button>
          </div>
        </div>

        <div className="searchbar">
          <Icon name="search" size={18} />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Поиск по заметкам"
            aria-label="Поиск по заметкам"
            enterKeyHint="search"
          />
          {search && (
            <button
              type="button"
              className="search-clear"
              onClick={() => setSearch("")}
              aria-label="Очистить поиск"
            >
              <Icon name="close" size={14} />
            </button>
          )}
        </div>

        <div className="chips chips-scroll">
          <button
            type="button"
            className={kind === "all" ? "chip active" : "chip"}
            onClick={() => setKind("all")}
          >
            Все
          </button>
          <button
            type="button"
            className={kind === "voice" ? "chip active" : "chip"}
            onClick={() => setKind("voice")}
          >
            <Icon name="mic" size={14} />
            Голос
          </button>
          <button
            type="button"
            className={kind === "text" ? "chip active" : "chip"}
            onClick={() => setKind("text")}
          >
            <Icon name="file" size={14} />
            Текст
          </button>
          <span className="chip-divider" aria-hidden="true" />
          <button
            type="button"
            className="chip chip-manage"
            onClick={() => setFoldersOpen(true)}
          >
            <Icon name="folderPlus" size={14} />
            Папки
          </button>
          {folders.map((folder) => (
            <button
              type="button"
              key={folder.id}
              className={folderId === folder.id ? "chip active" : "chip"}
              onClick={() =>
                setFolderId(folderId === folder.id ? null : folder.id)
              }
            >
              <Icon name="folder" size={14} />
              {folder.name}
            </button>
          ))}
        </div>

        {error && (
          <div className="inline-error">
            <Icon name="alert" size={18} />
            <span>{error}</span>
            <button type="button" className="btn-link" onClick={refresh}>
              Повторить
            </button>
          </div>
        )}

        {loading ? (
          <div className="skeleton-list" aria-hidden="true">
            {[0, 1, 2, 3].map((item) => (
              <div className="skeleton-card" key={item}>
                <div className="skeleton-icon" />
                <div className="skeleton-lines">
                  <div className="skeleton-line w-70" />
                  <div className="skeleton-line w-95" />
                  <div className="skeleton-line w-40" />
                </div>
              </div>
            ))}
          </div>
        ) : notes.length === 0 ? (
          <EmptyState
            filtered={filtersActive}
            onRecord={onRecord}
            onCompose={() => setComposerOpen(true)}
            onReset={resetFilters}
          />
        ) : (
          groups.map((group) => (
            <section className="note-group" key={group.key}>
              <h2 className="group-label">{group.label}</h2>
              <ul className="note-list">
                {group.items.map((note) => (
                  <li key={note.id}>
                    <NoteCard
                      note={note}
                      folderName={folderNameOf(note.folderId)}
                      onOpen={() => onOpen(note)}
                    />
                  </li>
                ))}
              </ul>
            </section>
          ))
        )}

        <div ref={sentinelRef} className="list-sentinel">
          {loadingMore && <span className="mini-spinner" />}
        </div>
      </div>

      <ComposerSheet
        open={composerOpen}
        folders={folders}
        initialFolderId={folderId}
        onClose={() => setComposerOpen(false)}
        onCreated={() => refresh()}
      />
      <FoldersSheet
        open={foldersOpen}
        folders={folders}
        onClose={() => setFoldersOpen(false)}
        onChanged={() => {
          void loadFolders();
          refresh();
        }}
      />
    </div>
  );
}

function NoteCard({
  note,
  folderName,
  onOpen,
}: {
  note: Note;
  folderName: string | null;
  onOpen: () => void;
}) {
  const processing = note.status === "processing";
  const errored = note.status === "error";
  const preview = processing
    ? "Расшифровываем запись…"
    : errored
      ? (note.errorMessage ?? "Не удалось расшифровать запись")
      : note.content.replace(/\s+/g, " ").trim();

  return (
    <button type="button" className="note-card" onClick={onOpen}>
      <span className={`note-icon ${note.kind === "voice" ? "voice" : ""}`}>
        <Icon name={note.kind === "voice" ? "mic" : "file"} size={18} />
      </span>
      <span className="note-body">
        <span className="note-top">
          <span className="note-title">{noteTitle(note)}</span>
          <span className="note-time">{formatRelative(note.createdAt)}</span>
        </span>
        {preview && <span className="note-preview">{preview}</span>}
        {(note.kind === "voice" || processing || errored || folderName) && (
          <span className="note-meta">
            {note.kind === "voice" && note.audioDurationSec ? (
              <span className="badge voice">
                <Icon name="clock" size={11} />
                {formatClock(note.audioDurationSec)}
              </span>
            ) : null}
            {processing && (
              <span className="badge processing">
                <span className="dot-pulse" />
                Расшифровка
              </span>
            )}
            {errored && (
              <span className="badge error">
                <Icon name="alert" size={11} />
                Ошибка
              </span>
            )}
            {folderName && (
              <span className="badge folder">
                <Icon name="folder" size={11} />
                {folderName}
              </span>
            )}
          </span>
        )}
      </span>
      <span className="note-chevron">
        <Icon name="chevronRight" size={16} />
      </span>
    </button>
  );
}

function EmptyState({
  filtered,
  onRecord,
  onCompose,
  onReset,
}: {
  filtered: boolean;
  onRecord: () => void;
  onCompose: () => void;
  onReset: () => void;
}) {
  if (filtered) {
    return (
      <div className="empty">
        <div className="empty-orb small">
          <Icon name="search" size={26} />
        </div>
        <h3>Ничего не нашлось</h3>
        <p>Попробуйте другой запрос или сбросьте фильтры.</p>
        <button type="button" className="btn btn-ghost" onClick={onReset}>
          Сбросить фильтры
        </button>
      </div>
    );
  }
  return (
    <div className="empty">
      <div className="empty-orb">
        <Icon name="wave" size={34} />
      </div>
      <h3>Здесь появятся ваши мысли</h3>
      <p>
        Запишите голосовую заметку — VoxDo расшифрует её в текст. Или создайте
        обычную текстовую.
      </p>
      <div className="empty-actions">
        <button type="button" className="btn btn-primary" onClick={onRecord}>
          <Icon name="mic" size={18} />
          Записать
        </button>
        <button type="button" className="btn btn-ghost" onClick={onCompose}>
          <Icon name="edit" size={17} />
          Текст
        </button>
      </div>
    </div>
  );
}
