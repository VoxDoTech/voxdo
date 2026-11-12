import { Note } from "@acme/db";
import { getDownloadUrl } from "@acme/storage";
import { and, eq } from "drizzle-orm";
import { z } from "zod";

import { protectedProcedure } from "../../orpc";

/**
 * Presigned GET URL for a voice note's original recording — owner only.
 * Expires in 1 hour.
 */
export const audioUrl = protectedProcedure
  .errors({
    NOT_FOUND: { message: "Аудио не найдено" },
  })
  .input(z.object({ id: z.uuid() }))
  .handler(async ({ context, input, errors }) => {
    const note = await context.db.query.Note.findFirst({
      where: and(
        eq(Note.id, input.id),
        eq(Note.userId, context.session.user.id),
      ),
    });
    if (!note?.audioKey) throw errors.NOT_FOUND();
    return {
      url: await getDownloadUrl(note.audioKey),
      mimeType: note.audioMimeType,
    };
  });
