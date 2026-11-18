import { Folder, Note } from "@acme/db";
import { and, eq } from "drizzle-orm";
import { z } from "zod";

import { protectedProcedure } from "../../orpc";

/**
 * Update a note's title, content or folder — owner only.
 */
export const update = protectedProcedure
  .errors({
    NOT_FOUND: { message: "Заметка не найдена" },
    BAD_REQUEST: { message: "Указанная папка не найдена" },
  })
  .input(
    z.object({
      id: z.uuid(),
      title: z.string().max(256).nullish(),
      content: z.string().max(100_000).optional(),
      folderId: z.uuid().nullish(),
    }),
  )
  .handler(async ({ context, input, errors }) => {
    const existing = await context.db.query.Note.findFirst({
      where: and(
        eq(Note.id, input.id),
        eq(Note.userId, context.session.user.id),
      ),
    });
    if (!existing) throw errors.NOT_FOUND();

    if (input.folderId) {
      const folder = await context.db.query.Folder.findFirst({
        where: and(
          eq(Folder.id, input.folderId),
          eq(Folder.userId, context.session.user.id),
        ),
      });
      if (!folder) throw errors.BAD_REQUEST();
    }

    const [note] = await context.db
      .update(Note)
      .set({
        ...(input.title !== undefined ? { title: input.title } : {}),
        ...(input.content !== undefined ? { content: input.content } : {}),
        ...(input.folderId !== undefined ? { folderId: input.folderId } : {}),
      })
      .where(eq(Note.id, input.id))
      .returning();
    if (!note) throw errors.NOT_FOUND();
    return note;
  });
