import { Folder } from "@acme/db";
import { z } from "zod";

import { protectedProcedure } from "../../orpc";

/**
 * Create a folder for the current user.
 */
export const create = protectedProcedure
  .input(z.object({ name: z.string().min(1).max(128) }))
  .handler(async ({ context, input }) => {
    const [folder] = await context.db
      .insert(Folder)
      .values({ userId: context.session.user.id, name: input.name.trim() })
      .returning();
    return folder;
  });
