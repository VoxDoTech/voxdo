import { sql } from "drizzle-orm";
import { pgTable } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod";

import { user } from "../auth/user";
import { Folder } from "./folder";

/**
 * Lifecycle of a voice note:
 * - `processing` — audio uploaded, transcription job running
 * - `ready`      — transcript (or user text) is in `content`
 * - `error`      — transcription failed; `errorMessage` has details
 */
export const NOTE_STATUSES = ["processing", "ready", "error"] as const;
export type NoteStatus = (typeof NOTE_STATUSES)[number];

export const Note = pgTable("notes", (t) => ({
  id: t.uuid().notNull().primaryKey().defaultRandom(),
  userId: t
    .text("user_id")
    .notNull()
    .references(() => user.id, { onDelete: "cascade" }),
  folderId: t
    .uuid("folder_id")
    .references(() => Folder.id, { onDelete: "set null" }),
  title: t.varchar({ length: 256 }),
  /** Transcript for voice notes, plain text for typed notes. */
  content: t.text().notNull().default(""),
  /** `voice` notes carry `audioKey`; `text` notes are typed. */
  kind: t.varchar({ length: 16 }).notNull().default("text"),
  status: t.varchar({ length: 16 }).notNull().default("ready"),
  /** S3 object key of the original recording. */
  audioKey: t.text("audio_key"),
  audioMimeType: t.text("audio_mime_type"),
  audioDurationSec: t.integer("audio_duration_sec"),
  errorMessage: t.text("error_message"),
  createdAt: t.timestamp({ withTimezone: true }).defaultNow().notNull(),
  updatedAt: t
    .timestamp({ mode: "date", withTimezone: true })
    .$onUpdateFn(() => sql`now()`),
}));

export const CreateNoteSchema = createInsertSchema(Note, {
  title: z.string().max(256).nullish(),
  content: z.string().max(100_000),
  folderId: z.uuid().nullish(),
})
  .omit({
    id: true,
    userId: true,
    kind: true,
    status: true,
    audioKey: true,
    audioMimeType: true,
    audioDurationSec: true,
    errorMessage: true,
    createdAt: true,
    updatedAt: true,
  })
  .extend({
    userId: z.string(),
  });
