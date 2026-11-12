"use client";

import { paths } from "@acme/config";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
  Badge,
  Button,
  Input,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Skeleton,
  Textarea,
  toast,
} from "@acme/ui";
import { IconArrowLeft, IconMicrophone, IconTrash } from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { formatDuration } from "~/lib/format";
import { orpc } from "~/orpc/react";

export function NoteDetail({ noteId }: { noteId: string }) {
  const noteQuery = useQuery(
    orpc.note.byId.queryOptions({
      input: { id: noteId },
      // Keep polling while GigaAM is still transcribing the recording.
      refetchInterval: (query) =>
        query.state.data?.status === "processing" ? 2500 : false,
    }),
  );
  const note = noteQuery.data;

  const isVoice = note?.kind === "voice";
  const audioQuery = useQuery({
    ...orpc.note.audioUrl.queryOptions({ input: { id: noteId } }),
    enabled: isVoice === true,
  });

  if (noteQuery.isPending) return <NoteDetailSkeleton />;
  if (noteQuery.isError || !note) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-destructive text-sm">Заметка не найдена.</p>
        <Button variant="outline" render={<Link href={paths.dashboard.root} />}>
          <IconArrowLeft />К заметкам
        </Button>
      </div>
    );
  }

  return (
    <NoteEditor
      key={note.id}
      note={note}
      audioUrl={audioQuery.data?.url ?? null}
    />
  );
}

function NoteEditor({
  note,
  audioUrl,
}: {
  note: {
    id: string;
    title: string | null;
    content: string;
    status: string;
    kind: string;
    errorMessage: string | null;
    folderId: string | null;
    audioDurationSec: number | null;
  };
  audioUrl: string | null;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState(note.title ?? "");
  const [content, setContent] = useState(note.content);
  const [folderId, setFolderId] = useState(note.folderId ?? "none");
  const [saved, setSaved] = useState(false);
  // Fields the user has touched must not be overwritten by polling.
  const contentDirty = useRef(false);
  const titleDirty = useRef(false);
  const folderDirty = useRef(false);

  // Fresh data arrives via the parent's polling — merge it into untouched
  // fields only, so in-progress typing is never overwritten.
  useEffect(() => {
    if (!contentDirty.current) setContent(note.content);
    if (!titleDirty.current) setTitle(note.title ?? "");
    if (!folderDirty.current) setFolderId(note.folderId ?? "none");
  }, [note]);

  const foldersQuery = useQuery(orpc.folder.list.queryOptions());
  const folders = foldersQuery.data ?? [];

  const updateNote = useMutation({
    ...orpc.note.update.mutationOptions(),
    onSuccess: async () => {
      contentDirty.current = false;
      titleDirty.current = false;
      folderDirty.current = false;
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
      await queryClient.invalidateQueries({ queryKey: orpc.note.key() });
    },
    onError: (err) => toast.error(err.message || "Не удалось сохранить"),
  });

  const deleteNote = useMutation({
    ...orpc.note.delete.mutationOptions(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: orpc.note.key() });
      router.push(paths.dashboard.root);
    },
    onError: (err) => toast.error(err.message || "Не удалось удалить"),
  });

  const dirty =
    title !== (note.title ?? "") ||
    content !== note.content ||
    folderId !== (note.folderId ?? "none");

  const duration = formatDuration(note.audioDurationSec);

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <Button
          variant="ghost"
          size="sm"
          render={<Link href={paths.dashboard.root} />}
        >
          <IconArrowLeft />К заметкам
        </Button>
        <AlertDialog>
          <AlertDialogTrigger
            render={<Button variant="destructive" size="sm" />}
          >
            <IconTrash />
            Удалить
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Удалить заметку?</AlertDialogTitle>
              <AlertDialogDescription>
                Заметка и её аудиозапись будут удалены безвозвратно.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Отмена</AlertDialogCancel>
              <AlertDialogAction
                disabled={deleteNote.isPending}
                onClick={() => deleteNote.mutate({ id: note.id })}
              >
                {deleteNote.isPending ? "Удаление…" : "Удалить"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {note.kind === "voice" && (
          <IconMicrophone className="text-muted-foreground size-5" />
        )}
        {note.status === "processing" && (
          <Badge variant="secondary">Транскрибируется…</Badge>
        )}
        {note.status === "error" && (
          <Badge variant="destructive">
            Ошибка транскрипции
            {note.errorMessage ? `: ${note.errorMessage}` : ""}
          </Badge>
        )}
        {duration && (
          <span className="text-muted-foreground text-sm">{duration}</span>
        )}
      </div>

      {audioUrl && (
        // biome-ignore lint/a11y/useMediaCaption: voice memo playback has no caption track
        <audio controls src={audioUrl} className="w-full" />
      )}

      <Input
        placeholder="Заголовок"
        value={title}
        onChange={(e) => {
          titleDirty.current = true;
          setTitle(e.target.value);
        }}
      />

      <Textarea
        value={content}
        onChange={(e) => {
          contentDirty.current = true;
          setContent(e.target.value);
        }}
        placeholder={
          note.status === "processing"
            ? "Ждите транскрипцию…"
            : "Текст заметки…"
        }
        className="min-h-64 text-base"
      />

      {folders.length > 0 && (
        <Select
          value={folderId}
          onValueChange={(v) => {
            folderDirty.current = true;
            setFolderId(v ?? "none");
          }}
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

      <div className="flex items-center gap-3">
        <Button
          disabled={!dirty || updateNote.isPending}
          onClick={() =>
            updateNote.mutate({
              id: note.id,
              title: title.trim() || null,
              content,
              folderId: folderId === "none" ? null : folderId,
            })
          }
        >
          {updateNote.isPending
            ? "Сохранение…"
            : saved
              ? "Сохранено"
              : "Сохранить"}
        </Button>
        {saved && (
          <span className="text-muted-foreground text-sm">Сохранено</span>
        )}
      </div>
    </div>
  );
}

function NoteDetailSkeleton() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
      <Skeleton className="h-9 w-32 rounded-md" />
      <Skeleton className="h-10 w-full rounded-md" />
      <Skeleton className="h-64 w-full rounded-md" />
    </div>
  );
}
