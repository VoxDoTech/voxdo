import { env, logger } from "@acme/config";
import { sendTemplateEmail, type TemplateEmail } from "@acme/emails";
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
 * Transcribes a voice note via GigaAM: through the `transcribe-audio`
 * Hatchet task when configured; otherwise — or if enqueueing fails — runs
 * the transcription right away in this process.
 */
export async function dispatchTranscription(
  input: TranscribeNoteInput,
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
  void transcribeNote(input).catch((error) => {
    logger.error("jobs.transcription_inline_failed", error, {
      noteId: input.noteId,
    });
  });
}
