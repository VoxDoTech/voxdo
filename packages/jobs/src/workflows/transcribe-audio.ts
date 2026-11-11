import { type TranscribeNoteInput, transcribeNote } from "../transcription";
import { hatchet } from "./client";

/**
 * Transcribes a voice note's audio via the self-hosted GigaAM service and
 * writes the transcript back to the note row.
 *
 * Enqueue it through `dispatchTranscription` from `@acme/jobs`, which runs
 * the same logic inline when Hatchet isn't configured.
 */
export const transcribeAudioTask = hatchet.task({
  name: "transcribe-audio",
  retries: 3,
  backoff: { factor: 2, maxSeconds: 120 },
  // Transcription of long memos can take a while on CPU.
  executionTimeout: "15m",
  fn: async (rawInput) => {
    const input = rawInput as unknown as TranscribeNoteInput;
    return transcribeNote(input);
  },
});
