import { env, logger } from "@acme/config";
import { sendTemplateEmail, type TemplateEmail } from "@acme/emails";
import { deleteFromS3 } from "@acme/storage";
import { type TranscribeNoteInput, transcribeNote } from "./transcription";

/**
 * App-facing entry of `@acme/jobs`: safe to import whether or not Hatchet is
 * configured. The Hatchet client (`./workflows`) is loaded lazily, only when
 * HATCHET_CLIENT_TOKEN is set — creating it without a token throws.
 */

/** Whether background work goes to Hatchet (HATCHET_CLIENT_TOKEN is set). */
export const jobsEnabled = Boolean(env.HATCHET_CLIENT_TOKEN);

/**
 * Sends a template email via the `send-email` Hatchet task (durable, with
 * retries) when Hatchet is configured; otherwise — or if enqueueing fails —
 * sends it right away in this process.
 */
export async function dispatchEmail(message: TemplateEmail): Promise<void> {
  if (jobsEnabled) {
    try {
      const { sendEmailTask } = await import("./workflows/send-email");
      await sendEmailTask.runNoWait(message);
      return;
    } catch (error) {
      logger.warn("jobs.enqueue_failed", {
        task: "send-email",
        template: message.template,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  await sendTemplateEmail(message);
}

/**
 * Registers fire-and-forget work so the surrounding request runtime keeps
 * the process alive until it settles — Next.js `after()` on Vercel.
 * Without it the promise still runs, but a serverless function may freeze
 * after the response and never finish the work.
 */
export type DeferWork = (promise: Promise<unknown>) => void;

/**
 * Transcribes a voice note via GigaAM: through the `transcribe-audio`
 * Hatchet task when configured; otherwise — or if enqueueing fails — runs
 * the transcription right away, registered via `defer` when the caller
 * provides one (the oRPC context does inside a Next.js request).
 */
export async function dispatchTranscription(
  input: TranscribeNoteInput,
  defer?: DeferWork,
): Promise<void> {
  if (jobsEnabled) {
    try {
      const { transcribeAudioTask } = await import(
        "./workflows/transcribe-audio"
      );
      await transcribeAudioTask.runNoWait(input);
      return;
    } catch (error) {
      logger.warn("jobs.enqueue_failed", {
        task: "transcribe-audio",
        noteId: input.noteId,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  // Inline fallback is fire-and-forget for the API caller: the note row is
  // already `processing`, and failures land in `error`/`errorMessage`.
  const work = transcribeNote(input).catch((error) => {
    logger.error("jobs.transcription_inline_failed", error, {
      noteId: input.noteId,
    });
  });
  if (defer) {
    defer(work);
  } else {
    void work;
  }
}

/**
 * Deletes a voice note's recording from S3: through the `delete-note-audio`
 * Hatchet task (with retries) when configured; otherwise deletes it right
 * away in this process.
 */
export async function dispatchAudioDeletion(audioKey: string): Promise<void> {
  if (jobsEnabled) {
    try {
      const { deleteAudioTask } = await import("./workflows/delete-audio");
      await deleteAudioTask.runNoWait({ audioKey });
      return;
    } catch (error) {
      logger.warn("jobs.enqueue_failed", {
        task: "delete-note-audio",
        audioKey,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  await deleteFromS3(audioKey).catch((error) => {
    logger.error("jobs.audio_delete_failed", error, { audioKey });
  });
}
