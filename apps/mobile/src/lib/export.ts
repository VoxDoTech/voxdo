import type { Note } from "../App";
import { api } from "./api";
import { formatClock, formatFull, noteTitle } from "./format";

export type ExportResult = "shared" | "copied" | "downloaded";

/**
 * The share sheet refused because the user activation expired while notes were
 * being fetched. The caller can retry `shareNotes` on the next tap.
 */
export class ShareActivationError extends Error {
  constructor() {
    super("Share activation expired");
    this.name = "ShareActivationError";
  }
}

/** Every note, paginated in batches of 100 until the last short page. */
export async function fetchAllNotes(): Promise<Note[]> {
  const all: Note[] = [];
  for (let offset = 0; ; offset += 100) {
    const batch = await api.note.list({ limit: 100, offset });
    all.push(...batch);
    if (batch.length < 100) break;
  }
  return all;
}

function notesToMarkdown(notes: Note[]): string {
  const lines: string[] = [
    "# VoxDo — заметки",
    `_Экспортировано ${formatFull(new Date())}_`,
    "",
  ];
  for (const note of notes) {
    lines.push(`## ${noteTitle(note)}`);
    const meta = [formatFull(note.createdAt)];
    if (note.kind === "voice") meta.push("голос");
    if (note.audioDurationSec) meta.push(formatClock(note.audioDurationSec));
    lines.push(`_${meta.join(" · ")}_`, "");
    lines.push(note.content.trim() || "_Без текста_", "");
  }
  return lines.join("\n");
}

/** Shares the notes as a Markdown file, falling back to clipboard/download. */
export async function shareNotes(notes: Note[]): Promise<ExportResult> {
  const markdown = notesToMarkdown(notes);
  const fileName = `voxdo-notes-${new Date().toISOString().slice(0, 10)}.md`;
  const file = new File([markdown], fileName, { type: "text/markdown" });

  if (navigator.canShare?.({ files: [file] })) {
    try {
      await navigator.share({
        files: [file],
        title: "VoxDo — заметки",
        text: `${notes.length} заметок из VoxDo`,
      });
      return "shared";
    } catch (cause) {
      // A user cancellation stays silent; an expired activation asks for one
      // more tap (the caller keeps the notes), and anything else falls back.
      if (cause instanceof DOMException) {
        if (cause.name === "AbortError") throw cause;
        if (cause.name === "NotAllowedError") throw new ShareActivationError();
      }
    }
  }

  try {
    await navigator.clipboard.writeText(markdown);
    return "copied";
  } catch {
    const url = URL.createObjectURL(file);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    link.click();
    URL.revokeObjectURL(url);
    return "downloaded";
  }
}
