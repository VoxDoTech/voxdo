import { Folder } from "@acme/db";
import { and, eq } from "drizzle-orm";
import { z } from "zod";

import { protectedProcedure } from "../../orpc";

/**
 * Rename a folder — owner only.
 */
export const update = protectedProcedure
  .errors({
    NOT_FOUND: { message: "Папка не найдена" },
  })
  .input(z.object({ id: z.uuid(), name: z.string().min(1).max(128) }))
  .handler(async ({ context, input, errors }) => {
    const [folder] = await context.db
      .update(Folder)
      .set({ name: input.name.trim() })
      .where(
        and(
          eq(Folder.id, input.id),
          eq(Folder.userId, context.session.user.id),
        ),
      )
      .returning();
    if (!folder) throw errors.NOT_FOUND();
    return folder;
  });
