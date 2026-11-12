import { Note } from "@acme/db";
import { and, eq } from "drizzle-orm";
import { z } from "zod";

import { protectedProcedure } from "../../orpc";

/**
 * Fetch a single note — owner only.
 */
export const byId = protectedProcedure
  .errors({
    NOT_FOUND: { message: "Заметка не найдена" },
  })
  .input(z.object({ id: z.uuid() }))
  .handler(async ({ context, input, errors }) => {
    const note = await context.db.query.Note.findFirst({
      where: and(
        eq(Note.id, input.id),
        eq(Note.userId, context.session.user.id),
      ),
    });
    if (!note) throw errors.NOT_FOUND();
    return note;
  });
