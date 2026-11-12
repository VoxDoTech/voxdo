import { Folder, Note } from "@acme/db";
import { and, eq } from "drizzle-orm";
import { z } from "zod";

import { protectedProcedure } from "../../orpc";

/**
 * Create a typed (non-voice) note.
 *
 * @example client.note.create({ title: "Идея", content: "…", folderId })
 */
export const create = protectedProcedure
  .errors({
    BAD_REQUEST: { message: "Указанная папка не найдена" },
  })
  .input(
    z.object({
      title: z.string().max(256).optional(),
      content: z.string().max(100_000).default(""),
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

    const [note] = await context.db
      .insert(Note)
      .values({
        userId: context.session.user.id,
        title: input.title ?? null,
        content: input.content,
        folderId: input.folderId ?? null,
        kind: "text",
        status: "ready",
      })
      .returning();
    return note;
  });
