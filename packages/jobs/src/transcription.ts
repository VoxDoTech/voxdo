import { env, logger } from "@acme/config";
import { db, Note } from "@acme/db";
import { downloadFromS3 } from "@acme/storage";
import { eq, sql } from "drizzle-orm";

export interface TranscribeNoteInput {
  noteId: string;
  audioKey: string;
}

export interface TranscribeNoteOptions {
  /**
   * Whether this is the last attempt. While retries remain the note stays
   * `processing` so clients keep polling; `error` is only written once no
   * retry can still succeed. Defaults to `true` (inline execution has no
   * retries).
   */
  finalAttempt?: boolean;
}

interface GigaAmSegment {
  text?: string;
}

interface GigaAmResponse {
  success?: boolean;
  segments?: GigaAmSegment[];
  detail?: string;
  error?: string;
}

/** Upper bound for a single GigaAM request — long memos on CPU are slow. */
const GIGA_AM_TIMEOUT_MS = 10 * 60 * 1000;

/**
 * Downloads the recording from S3, sends it to the GigaAM
 * `/api/transcribe-sync` endpoint and writes the transcript back to the
 * note. Shared by the Hatchet task and the inline fallback — safe to call
 * from `@acme/jobs` without a Hatchet token.
 */
export async function transcribeNote(
  input: TranscribeNoteInput,
  opts: TranscribeNoteOptions = {},
): Promise<{
  noteId: string;
  chars: number;
}> {
  const finalAttempt = opts.finalAttempt ?? true;
  const baseUrl = env.GIGA_AM_URL;
  if (!baseUrl) {
    await fail(input.noteId, "GIGA_AM_URL is not configured", finalAttempt);
    throw new Error("GIGA_AM_URL is not configured");
  }

  try {
    const audio = await downloadFromS3(input.audioKey);
    const form = new FormData();
    form.append(
      "file",
      new Blob([new Uint8Array(audio)], {
        type: "application/octet-stream",
      }),
      input.audioKey.split("/").pop() ?? "audio.webm",
    );
    form.append("filename", input.audioKey.split("/").pop() ?? "audio.webm");

    const res = await fetch(
      `${baseUrl.replace(/\/$/, "")}/api/transcribe-sync`,
      {
        method: "POST",
        body: form,
        signal: AbortSignal.timeout(GIGA_AM_TIMEOUT_MS),
      },
    );
    const body = (await res.json().catch(() => null)) as GigaAmResponse | null;

    if (!res.ok || !body?.success) {
      const message =
        body?.detail ?? body?.error ?? `GigaAM responded ${res.status}`;
      await fail(input.noteId, message, finalAttempt);
      throw new Error(`Transcription failed: ${message}`);
    }

    const transcript = (body.segments ?? [])
      .map((s) => s.text?.trim())
      .filter(Boolean)
      .join(" ")
      .replace(/\s+/g, " ")
      .trim();

    // Fill `content`/`title` only where the user hasn't typed anything —
    // edits made while the note was `processing` must survive the write.
    await db
      .update(Note)
      .set({
        status: "ready",
        errorMessage: null,
        content: sql`CASE WHEN btrim(${Note.content}) = '' THEN ${transcript} ELSE ${Note.content} END`,
        // Auto-title voice notes from the first words of the transcript.
        title: sql`CASE WHEN (${Note.title} IS NULL OR ${Note.title} = '') AND ${transcript} <> '' THEN ${transcript.slice(0, 80)} ELSE ${Note.title} END`,
      })
      .where(eq(Note.id, input.noteId));

    logger.info("jobs.transcription_done", {
      noteId: input.noteId,
      chars: transcript.length,
    });
    return { noteId: input.noteId, chars: transcript.length };
  } catch (error) {
    // fail already ran for API failures; cover network/S3 errors too.
    if (
      error instanceof Error &&
      !error.message.startsWith("Transcription failed") &&
      error.message !== "GIGA_AM_URL is not configured"
    ) {
      await fail(input.noteId, error.message, finalAttempt).catch(
        () => undefined,
      );
    }
    throw error;
  }
}

/**
 * Marks the note failed — but only on the final attempt. Earlier failures
 * leave the note `processing` so the UI keeps polling through Hatchet
 * retries.
 */
async function fail(
  noteId: string,
  message: string,
  finalAttempt: boolean,
): Promise<void> {
  if (!finalAttempt) {
    logger.warn("jobs.transcription_retry", { noteId, error: message });
    return;
  }
  await markError(noteId, message);
}

async function markError(noteId: string, message: string): Promise<void> {
  await db
    .update(Note)
    .set({ status: "error", errorMessage: message.slice(0, 1000) })
    .where(eq(Note.id, noteId));
  logger.warn("jobs.transcription_failed", { noteId, error: message });
}
