import { pgTable } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod";

import { user } from "../auth/user";

export const Folder = pgTable("folders", (t) => ({
  id: t.uuid().notNull().primaryKey().defaultRandom(),
  userId: t
    .text("user_id")
    .notNull()
    .references(() => user.id, { onDelete: "cascade" }),
  name: t.varchar({ length: 128 }).notNull(),
  createdAt: t.timestamp({ withTimezone: true }).defaultNow().notNull(),
}));

export const CreateFolderSchema = createInsertSchema(Folder, {
  name: z.string().min(1).max(128),
})
  .omit({
    id: true,
    userId: true,
    createdAt: true,
  })
  .extend({
    userId: z.string(),
  });
