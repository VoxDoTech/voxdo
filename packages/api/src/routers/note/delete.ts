import { Note } from "@acme/db";
import { dispatchAudioDeletion } from "@acme/jobs";
import { and, eq } from "drizzle-orm";
import { z } from "zod";

import { protectedProcedure } from "../../orpc";

/**
 * Delete a note — owner only. The recording is removed from S3 through a
 * retryable cleanup task so deleted voice notes don't leave audio behind.
 */
export const deleteNote = protectedProcedure
  .errors({
    NOT_FOUND: { message: "Заметка не найдена" },
  })
  .input(z.object({ id: z.uuid() }))
  .handler(async ({ context, input, errors }) => {
    const [deleted] = await context.db
      .delete(Note)
      .where(
        and(eq(Note.id, input.id), eq(Note.userId, context.session.user.id)),
      )
      .returning({ id: Note.id, audioKey: Note.audioKey });
    if (!deleted) throw errors.NOT_FOUND();

    if (deleted.audioKey) {
      await dispatchAudioDeletion(deleted.audioKey);
    }
    return { ok: true };
  });
