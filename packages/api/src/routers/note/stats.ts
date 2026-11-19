import { Folder, Note } from "@acme/db";
import { eq, sql } from "drizzle-orm";

import { protectedProcedure } from "../../orpc";

/**
 * Aggregate counters for the current user's notes — powers the mobile
 * profile screen without downloading every note.
 *
 * @example client.note.stats()
 */
export const stats = protectedProcedure.handler(async ({ context }) => {
  const [notes] = await context.db
    .select({
      total: sql<number>`count(*)`.mapWith(Number),
      voice:
        sql<number>`count(*) filter (where ${Note.kind} = 'voice')`.mapWith(
          Number,
        ),
      text: sql<number>`count(*) filter (where ${Note.kind} = 'text')`.mapWith(
        Number,
      ),
      processing:
        sql<number>`count(*) filter (where ${Note.status} = 'processing')`.mapWith(
          Number,
        ),
      audioSeconds:
        sql<number>`coalesce(sum(${Note.audioDurationSec}), 0)`.mapWith(Number),
    })
    .from(Note)
    .where(eq(Note.userId, context.session.user.id));

  const [folders] = await context.db
    .select({ total: sql<number>`count(*)`.mapWith(Number) })
    .from(Folder)
    .where(eq(Folder.userId, context.session.user.id));

  return {
    notes: notes?.total ?? 0,
    voice: notes?.voice ?? 0,
    text: notes?.text ?? 0,
    processing: notes?.processing ?? 0,
    audioSeconds: notes?.audioSeconds ?? 0,
    folders: folders?.total ?? 0,
  };
});
