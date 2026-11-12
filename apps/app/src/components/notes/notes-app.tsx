"use client";

import { paths } from "@acme/config";
import {
  Badge,
  Button,
  Input,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Textarea,
  toast,
} from "@acme/ui";
import {
  IconCheck,
  IconFolder,
  IconFolderPlus,
  IconMicrophone,
  IconPlus,
  IconSearch,
  IconX,
} from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { formatNoteDate } from "~/lib/format";
import { type RecordedAudio, VoiceRecorder } from "~/lib/voice-recorder";
import { orpc } from "~/orpc/react";

const PAGE_SIZE = 50;

function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

export function NotesApp() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);
  const [folderFilter, setFolderFilter] = useState<string>("all");
  const [pages, setPages] = useState(1);
  const [showNew, setShowNew] = useState(false);
  const [showFolders, setShowFolders] = useState(false);

  // Filters reset pagination back to the first page — adjusted during render
  // instead of an effect so a stale page can't show through one frame.
  const filterKey = `${folderFilter}${debouncedSearch}`;
  const [prevFilterKey, setPrevFilterKey] = useState(filterKey);
  if (prevFilterKey !== filterKey) {
    setPrevFilterKey(filterKey);
    setPages(1);
  }

  const foldersQuery = useQuery(orpc.folder.list.queryOptions());
  const folders = foldersQuery.data ?? [];

  const notesQuery = useQuery(
    orpc.note.list.queryOptions({
      input: {
        folderId: folderFilter === "all" ? undefined : folderFilter,
        q: debouncedSearch.trim() || undefined,
        limit: PAGE_SIZE * pages,
        offset: 0,
      },
    }),
  );
  const notes = notesQuery.data ?? [];
  const hasMore = notes.length === PAGE_SIZE * pages;

  const folderNameOf = (id: string | null) =>
    id ? (folders.find((f) => f.id === id)?.name ?? null) : null;

  return (
    <div className="flex flex-1 flex-col gap-4 p-4 md:gap-6 md:p-6">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-48 flex-1">
          <IconSearch className="text-muted-foreground absolute top-1/2 left-2.5 size-4 -translate-y-1/2" />
          <Input
            placeholder="Поиск по заметкам…"
            className="pl-8"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select
          value={folderFilter}
          onValueChange={(v) => setFolderFilter(v ?? "all")}
        >
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Все папки" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Все папки</SelectItem>
            {folders.map((f) => (
              <SelectItem key={f.id} value={f.id}>
                {f.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          variant={showFolders ? "secondary" : "outline"}
          onClick={() => setShowFolders((v) => !v)}
        >
          <IconFolder />
          Папки
        </Button>
        <VoiceNoteButton
          onUploaded={() =>
            queryClient.invalidateQueries({ queryKey: orpc.note.key() })
          }
        />
        <Button onClick={() => setShowNew((v) => !v)}>
          <IconPlus />
          Заметка
        </Button>
      </div>

      {showFolders && (
        <FoldersPanel
          folders={folders}
          onChanged={() =>
            queryClient.invalidateQueries({ queryKey: orpc.folder.key() })
          }
        />
      )}

      {showNew && (
        <NewNoteForm
          folders={folders}
          defaultFolderId={folderFilter === "all" ? undefined : folderFilter}
          onCreated={() => {
            setShowNew(false);
            void queryClient.invalidateQueries({
              queryKey: orpc.note.key(),
            });
          }}
          onCancel={() => setShowNew(false)}
        />
      )}

      {notesQuery.isPending ? (
        <NotesSkeleton />
      ) : notesQuery.isError ? (
        <p className="text-destructive text-sm">
          Не удалось загрузить заметки. Попробуйте обновить страницу.
        </p>
      ) : notes.length === 0 ? (
        <div className="text-muted-foreground rounded-xl border border-dashed p-10 text-center text-sm">
          Пока пусто. Создайте текстовую заметку или запишите голосовую.
        </div>
      ) : (
        <ul className="grid gap-3">
          {notes.map((note) => (
            <li key={note.id}>
              <Link
                href={paths.notes.detail(note.id)}
                className="hover:bg-accent/50 block rounded-xl border p-4 transition-colors"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      {note.kind === "voice" && (
                        <IconMicrophone className="text-muted-foreground size-4 shrink-0" />
                      )}
                      <span className="truncate font-medium">
                        {note.title ??
                          (note.content
                            ? note.content.slice(0, 60)
                            : "Без названия")}
                      </span>
                    </div>
                    {note.title && note.content && (
                      <p className="text-muted-foreground mt-1 line-clamp-2 text-sm">
                        {note.status === "processing"
                          ? "Транскрибируется…"
                          : note.content.slice(0, 120)}
                      </p>
                    )}
                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      {note.status === "processing" && (
                        <Badge variant="secondary">Транскрибируется…</Badge>
                      )}
                      {note.status === "error" && (
                        <Badge variant="destructive">Ошибка</Badge>
                      )}
                      {folderNameOf(note.folderId) && (
                        <Badge variant="outline">
                          <IconFolder />
                          {folderNameOf(note.folderId)}
                        </Badge>
                      )}
                      <span className="text-muted-foreground ml-auto text-xs">
                        {formatNoteDate(note.createdAt)}
                      </span>
                    </div>
                  </div>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {hasMore && !notesQuery.isPending && (
        <Button
          variant="outline"
          className="self-center"
          disabled={notesQuery.isFetching}
          onClick={() => setPages((p) => p + 1)}
        >
          {notesQuery.isFetching ? "Загрузка…" : "Загрузить ещё"}
        </Button>
      )}
    </div>
  );
}

function NotesSkeleton() {
  return (
    <ul className="grid gap-3">
      {Array.from({ length: 4 }).map((_, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton list
        <li key={i} className="h-20 animate-pulse rounded-xl border" />
      ))}
    </ul>
  );
}

function NewNoteForm({
  folders,
  defaultFolderId,
  onCreated,
  onCancel,
}: {
  folders: { id: string; name: string }[];
  defaultFolderId?: string;
  onCreated: () => void;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [folderId, setFolderId] = useState(defaultFolderId ?? "none");

  const createNote = useMutation({
    ...orpc.note.create.mutationOptions(),
    onSuccess: onCreated,
    onError: (err) => toast.error(err.message || "Не удалось сохранить"),
  });

  const canSave = Boolean(title.trim() || content.trim());

  return (
    <div className="flex flex-col gap-3 rounded-xl border p-4">
      <Input
        placeholder="Заголовок (необязательно)"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
      />
      <Textarea
        placeholder="Текст заметки…"
        rows={4}
        value={content}
        onChange={(e) => setContent(e.target.value)}
      />
      {folders.length > 0 && (
        <Select
          value={folderId}
          onValueChange={(v) => setFolderId(v ?? "none")}
        >
          <SelectTrigger className="w-full">
            <SelectValue placeholder="Папка" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none">Без папки</SelectItem>
            {folders.map((f) => (
              <SelectItem key={f.id} value={f.id}>
                {f.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}
      <div className="flex gap-2">
        <Button
          disabled={!canSave || createNote.isPending}
          onClick={() =>
            createNote.mutate({
              title: title.trim() || undefined,
              content: content.trim(),
              folderId: folderId === "none" ? undefined : folderId,
            })
          }
        >
          {createNote.isPending ? "Сохранение…" : "Сохранить"}
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Отмена
        </Button>
      </div>
    </div>
  );
}

function FoldersPanel({
  folders,
  onChanged,
}: {
  folders: { id: string; name: string }[];
  onChanged: () => void;
}) {
  const [name, setName] = useState("");

  const createFolder = useMutation({
    ...orpc.folder.create.mutationOptions(),
    onSuccess: () => {
      setName("");
      onChanged();
    },
    onError: (err) => toast.error(err.message || "Не удалось создать папку"),
  });
  const deleteFolder = useMutation({
    ...orpc.folder.delete.mutationOptions(),
    onSuccess: onChanged,
    onError: (err) => toast.error(err.message || "Не удалось удалить папку"),
  });

  return (
    <div className="flex flex-col gap-3 rounded-xl border p-4">
      <div className="flex flex-wrap items-center gap-2">
        {folders.map((f) => (
          <Badge key={f.id} variant="secondary" className="gap-1 pr-1">
            {f.name}
            <button
              type="button"
              aria-label={`Удалить папку ${f.name}`}
              className="hover:text-destructive rounded-full p-0.5"
              disabled={deleteFolder.isPending}
              onClick={() => deleteFolder.mutate({ id: f.id })}
            >
              <IconX className="size-3" />
            </button>
          </Badge>
        ))}
        {folders.length === 0 && (
          <span className="text-muted-foreground text-sm">Папок пока нет.</span>
        )}
      </div>
      <div className="flex gap-2">
        <Input
          placeholder="Новая папка…"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && name.trim()) {
              createFolder.mutate({ name: name.trim() });
            }
          }}
        />
        <Button
          variant="outline"
          disabled={!name.trim() || createFolder.isPending}
          onClick={() => createFolder.mutate({ name: name.trim() })}
        >
          <IconFolderPlus />
          Создать
        </Button>
      </div>
    </div>
  );
}

type RecPhase = "idle" | "starting" | "recording" | "uploading" | "error";

function VoiceNoteButton({ onUploaded }: { onUploaded: () => void }) {
  const recorderRef = useRef<VoiceRecorder | null>(null);
  const mountedRef = useRef(true);
  const [phase, setPhase] = useState<RecPhase>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [pendingAudio, setPendingAudio] = useState<RecordedAudio | null>(null);

  const createVoice = useMutation({
    ...orpc.note.createVoice.mutationOptions(),
    onSuccess: () => {
      setPendingAudio(null);
      setPhase("idle");
      onUploaded();
      toast.success("Запись сохранена — транскрибируется…");
    },
    onError: (err) => {
      setError(err.message || "Не удалось сохранить");
      setPhase("error");
    },
  });

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      recorderRef.current?.cancel();
      recorderRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (phase !== "recording") return;
    const timer = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, [phase]);

  const upload = async (audio: RecordedAudio) => {
    setPhase("uploading");
    setError(null);
    // Kept for retry if the upload fails — cleared on success.
    setPendingAudio(audio);
    try {
      await createVoice.mutateAsync({
        audioBase64: audio.base64,
        mimeType: audio.mimeType,
        durationSec: audio.durationSec,
      });
    } catch {
      // Error state is set by the mutation's onError.
    }
  };

  const start = async () => {
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

  const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");

  if (phase === "recording" || phase === "uploading" || phase === "starting") {
    return (
      <div className="flex items-center gap-2">
        <span className="text-destructive text-sm font-medium">
          {phase === "recording" ? "●" : "…"} {mm}:{ss}
        </span>
        {phase === "recording" && (
          <>
            <Button size="sm" variant="ghost" onClick={cancel}>
              <IconX />
              Отмена
            </Button>
            <Button size="sm" onClick={() => void stopAndSave()}>
              <IconCheck />
              Готово
            </Button>
          </>
        )}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <Button variant="outline" onClick={() => void start()}>
        <IconMicrophone />
        Записать
      </Button>
      {phase === "error" && error && (
        <span className="text-destructive max-w-48 truncate text-xs">
          {error}
        </span>
      )}
      {pendingAudio && phase === "error" && (
        <Button
          size="sm"
          variant="secondary"
          onClick={() => void upload(pendingAudio)}
        >
          Повторить
        </Button>
      )}
    </div>
  );
}
