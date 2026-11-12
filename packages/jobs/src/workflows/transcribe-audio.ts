import { type TranscribeNoteInput, transcribeNote } from "../transcription";
import { hatchet } from "./client";

/** Total attempts = 1 + retries; `error` is only written on the last one. */
const MAX_RETRIES = 3;

/**
 * Transcribes a voice note's audio via the self-hosted GigaAM service and
 * writes the transcript back to the note row.
 *
 * Enqueue it through `dispatchTranscription` from `@acme/jobs`, which runs
 * the same logic inline when Hatchet isn't configured.
 */
export const transcribeAudioTask = hatchet.task({
  name: "transcribe-audio",
  retries: MAX_RETRIES,
  backoff: { factor: 2, maxSeconds: 120 },
  // Transcription of long memos can take a while on CPU.
  executionTimeout: "15m",
  fn: async (rawInput, ctx) => {
    const input = rawInput as unknown as TranscribeNoteInput;
    return transcribeNote(input, {
      finalAttempt: ctx.retryCount() >= MAX_RETRIES,
    });
  },
});
