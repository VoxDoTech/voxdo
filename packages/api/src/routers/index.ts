/**
 * Root Router
 *
 * The single entry-point for the entire oRPC API.
 * Add new domain routers here and they become available everywhere
 * (Next.js handler, RSC clients, type-safe hooks, etc.).
 *
 * Current route map:
 *
 *   user.*          – current user profile & account settings  (protected)
 *   post.list       – paginated list of posts                  (public)
 *   post.byId       – single post by UUID                      (public)
 *   post.create     – create a post                            (protected)
 *   post.delete     – delete a post                            (admin)
 *   admin.users.*   – user management                          (admin)
 *   admin.stats.*   – system-wide statistics                   (admin)
 *   note.*          – voice/text notes (SecondBrain-style)     (protected)
 *   folder.*        – note folders                             (protected)
 */

import { adminRouter } from "./admin";
import { folderRouter } from "./folder";
import { noteRouter } from "./note";
import { postRouter } from "./post";
import { userRouter } from "./user";

export const appRouter = {
  user: userRouter,
  post: postRouter,
  admin: adminRouter,
  note: noteRouter,
  folder: folderRouter,
};

export type AppRouter = typeof appRouter;
