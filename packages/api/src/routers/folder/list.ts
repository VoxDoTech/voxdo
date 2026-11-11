import { Folder } from "@acme/db";
import { eq } from "drizzle-orm";

import { protectedProcedure } from "../../orpc";

/**
 * List the current user's folders.
 */
export const list = protectedProcedure.handler(async ({ context }) => {
  return context.db.query.Folder.findMany({
    where: eq(Folder.userId, context.session.user.id),
    orderBy: (folders, { asc }) => [asc(folders.name)],
  });
});
