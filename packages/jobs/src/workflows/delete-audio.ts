import { deleteFromS3 } from "@acme/storage";

import { hatchet } from "./client";

/**
 * Deletes a voice note's recording from S3 after the note row is gone.
 *
 * Enqueue it through `dispatchAudioDeletion` from `@acme/jobs`, which
 * deletes inline when Hatchet isn't configured.
 */
export const deleteAudioTask = hatchet.task({
  name: "delete-note-audio",
  retries: 5,
  backoff: { factor: 2, maxSeconds: 300 },
  executionTimeout: "1m",
  fn: async (rawInput) => {
    const { audioKey } = rawInput as { audioKey: string };
    await deleteFromS3(audioKey);
    return { audioKey };
  },
});
