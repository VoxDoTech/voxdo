import { Note } from "@acme/db";
import { and, eq } from "drizzle-orm";
import { z } from "zod";

import { protectedProcedure } from "../../orpc";

/**
 * Delete a note — owner only.
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
      .returning({ id: Note.id });
    if (!deleted) throw errors.NOT_FOUND();
    return { ok: true };
  });
