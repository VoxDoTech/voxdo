import { Folder } from "@acme/db";
import { and, eq } from "drizzle-orm";
import { z } from "zod";

import { protectedProcedure } from "../../orpc";

/**
 * Delete a folder — owner only. Notes inside keep existing with
 * `folderId = null` (FK ON DELETE SET NULL).
 */
export const deleteFolder = protectedProcedure
  .errors({
    NOT_FOUND: { message: "Папка не найдена" },
  })
  .input(z.object({ id: z.uuid() }))
  .handler(async ({ context, input, errors }) => {
    const [deleted] = await context.db
      .delete(Folder)
      .where(
        and(
          eq(Folder.id, input.id),
          eq(Folder.userId, context.session.user.id),
        ),
      )
      .returning({ id: Folder.id });
    if (!deleted) throw errors.NOT_FOUND();
    return { ok: true };
  });
