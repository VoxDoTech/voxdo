import { env, logger } from "@acme/config";
import { db, Note } from "@acme/db";
import { downloadFromS3 } from "@acme/storage";
import { eq } from "drizzle-orm";

export interface TranscribeNoteInput {
  noteId: string;
  audioKey: string;
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

/**
 * Downloads the recording from S3, sends it to the GigaAM
 * `/api/transcribe-sync` endpoint and writes the transcript back to the
 * note. Shared by the Hatchet task and the inline fallback — safe to call
 * from `@acme/jobs` without a Hatchet token.
 */
export async function transcribeNote(input: TranscribeNoteInput): Promise<{
  noteId: string;
  chars: number;
}> {
  const baseUrl = env.GIGA_AM_URL;
  if (!baseUrl) {
    await markError(input.noteId, "GIGA_AM_URL is not configured");
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
      },
    );
    const body = (await res.json().catch(() => null)) as GigaAmResponse | null;

    if (!res.ok || !body?.success) {
      const message =
        body?.detail ?? body?.error ?? `GigaAM responded ${res.status}`;
      await markError(input.noteId, message);
      throw new Error(`Transcription failed: ${message}`);
    }

    const transcript = (body.segments ?? [])
      .map((s) => s.text?.trim())
      .filter(Boolean)
      .join(" ")
      .replace(/\s+/g, " ")
      .trim();

    const [note] = await db
      .select({ title: Note.title })
      .from(Note)
      .where(eq(Note.id, input.noteId))
      .limit(1);

    await db
      .update(Note)
      .set({
        content: transcript,
        status: "ready",
        errorMessage: null,
        // Auto-title voice notes from the first words of the transcript.
        ...(note && !note.title && transcript
          ? { title: transcript.slice(0, 80) }
          : {}),
      })
      .where(eq(Note.id, input.noteId));

    logger.info("jobs.transcription_done", {
      noteId: input.noteId,
      chars: transcript.length,
    });
    return { noteId: input.noteId, chars: transcript.length };
  } catch (error) {
    // markError already ran for API failures; cover network/S3 errors too.
    if (
      error instanceof Error &&
      !error.message.startsWith("Transcription failed")
    ) {
      await markError(input.noteId, error.message).catch(() => undefined);
    }
    throw error;
  }
}

async function markError(noteId: string, message: string): Promise<void> {
  await db
    .update(Note)
    .set({ status: "error", errorMessage: message.slice(0, 1000) })
    .where(eq(Note.id, noteId));
  logger.warn("jobs.transcription_failed", { noteId, error: message });
}
