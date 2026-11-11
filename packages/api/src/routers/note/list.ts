import { Note } from "@acme/db";
import { and, eq, ilike, or } from "drizzle-orm";
import { z } from "zod";

import { protectedProcedure } from "../../orpc";

/**
 * List the current user's notes, newest first.
 *
 * @example client.note.list({ folderId: "…", q: "идея" })
 */
export const list = protectedProcedure
  .input(
    z.object({
      folderId: z.uuid().optional(),
      /** Case-insensitive substring match on title + content. */
      q: z.string().max(200).optional(),
      limit: z.number().min(1).max(100).default(50),
      offset: z.number().min(0).default(0),
    }),
  )
  .handler(async ({ context, input }) => {
    const pattern = input.q
      ? `%${input.q.replaceAll("\\", "\\\\").replaceAll("%", "\\%").replaceAll("_", "\\_")}%`
      : undefined;

    return context.db.query.Note.findMany({
      where: and(
        eq(Note.userId, context.session.user.id),
        input.folderId ? eq(Note.folderId, input.folderId) : undefined,
        pattern
          ? or(ilike(Note.title, pattern), ilike(Note.content, pattern))
          : undefined,
      ),
      limit: input.limit,
      offset: input.offset,
      orderBy: (notes, { desc }) => [desc(notes.createdAt)],
    });
  });
