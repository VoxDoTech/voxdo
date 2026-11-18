import { Folder, Note, sql, user } from "@acme/db";

import { adminProcedure } from "../../../orpc";

/**
 * High-level system overview: user, note and folder counts.
 *
 * Uses COUNT(*) aggregates for efficiency — no full table scans.
 *
 * @example client.admin.stats.overview()
 */
export const overview = adminProcedure.handler(async ({ context }) => {
  const [userRow] = await context.db
    .select({ count: sql<number>`count(*)::int` })
    .from(user);

  const [noteRow] = await context.db
    .select({ count: sql<number>`count(*)::int` })
    .from(Note);

  const [folderRow] = await context.db
    .select({ count: sql<number>`count(*)::int` })
    .from(Folder);

  return {
    users: userRow?.count ?? 0,
    notes: noteRow?.count ?? 0,
    folders: folderRow?.count ?? 0,
  };
});
