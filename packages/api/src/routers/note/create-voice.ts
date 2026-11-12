import { Folder, Note } from "@acme/db";
import { dispatchTranscription } from "@acme/jobs";
import { deleteFromS3, generateS3Key, uploadBufferToS3 } from "@acme/storage";
import { and, eq } from "drizzle-orm";
import { z } from "zod";

import { protectedProcedure } from "../../orpc";

/** ~20 MB of binary audio as base64 — covers long voice memos. */
const MAX_AUDIO_BASE64_LENGTH = 30_000_000;

/**
 * Create a voice note from a recorded audio clip.
 *
 * The audio arrives base64-encoded (MediaRecorder output from the mobile
 * app), is stored in S3, and a transcription job is dispatched. The note is
 * returned immediately with `status: "processing"` — poll `note.byId` until
 * it becomes `ready` (or `error`).
 *
 * @example client.note.createVoice({ audioBase64, mimeType: "audio/webm" })
 */
export const createVoice = protectedProcedure
  .errors({
    BAD_REQUEST: { message: "Некорректные аудио данные" },
    UPLOAD_FAILED: { message: "Не удалось сохранить аудио" },
  })
  .input(
    z.object({
      /** Base64-encoded audio blob (no data: URL prefix required). */
      audioBase64: z.string().min(1).max(MAX_AUDIO_BASE64_LENGTH),
      mimeType: z.string().min(3).max(100).default("audio/webm"),
      durationSec: z.number().min(0).max(86_400).optional(),
      title: z.string().max(256).optional(),
      folderId: z.uuid().optional(),
    }),
  )
  .handler(async ({ context, input, errors }) => {
    if (input.folderId) {
      const folder = await context.db.query.Folder.findFirst({
        where: and(
          eq(Folder.id, input.folderId),
          eq(Folder.userId, context.session.user.id),
        ),
      });
      if (!folder) throw errors.BAD_REQUEST();
    }

    const audio = Buffer.from(input.audioBase64, "base64");
    if (audio.length === 0) throw errors.BAD_REQUEST();

    const ext =
      input.mimeType.includes("mp4") || input.mimeType.includes("m4a")
        ? "m4a"
        : input.mimeType.includes("mpeg") || input.mimeType.includes("mp3")
          ? "mp3"
          : input.mimeType.includes("wav")
            ? "wav"
            : input.mimeType.includes("ogg")
              ? "ogg"
              : "webm";
    const audioKey = generateS3Key(`voice-note.${ext}`);

    try {
      await uploadBufferToS3(audioKey, audio, input.mimeType);
    } catch {
      throw errors.UPLOAD_FAILED();
    }

    const [note] = await context.db
      .insert(Note)
      .values({
        userId: context.session.user.id,
        folderId: input.folderId ?? null,
        title: input.title ?? null,
        kind: "voice",
        status: "processing",
        audioKey,
        audioMimeType: input.mimeType,
        audioDurationSec: input.durationSec ?? null,
      })
      .returning()
      .catch(async (error) => {
        // Compensating cleanup: don't leave an orphaned upload behind.
        await deleteFromS3(audioKey).catch(() => undefined);
        throw error;
      });
    if (!note) {
      await deleteFromS3(audioKey).catch(() => undefined);
      throw errors.UPLOAD_FAILED();
    }

    await dispatchTranscription({ noteId: note.id, audioKey }, context.defer);

    return note;
  });
