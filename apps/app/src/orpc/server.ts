import "server-only";

import { appRouter, createORPCContext } from "@acme/api";
import { createRouterClient } from "@orpc/server";
import { createTanstackQueryUtils } from "@orpc/tanstack-query";
import { headers } from "next/headers";
import { after } from "next/server";
import { cache } from "react";
import { auth } from "~/auth/server";

const createServerContext = cache(async () => {
  const heads = new Headers(await headers());
  heads.set("x-orpc-source", "rsc");

  const session = await auth.api.getSession({ headers: heads });

  return createORPCContext({
    headers: heads,
    session,
    // Same background-work hook as the route handler: `after` only works
    // inside a request, elsewhere the promise just runs unawaited.
    defer: (promise) => {
      try {
        after(promise);
      } catch {
        void promise;
      }
    },
  });
});

/**
 * This is part of the Optimize SSR setup.
 *
 * @see {@link https://orpc.dev/docs/adapters/next#optimize-ssr}
 */
globalThis.$client = createRouterClient(appRouter, {
  context: createServerContext,
});

export const api = globalThis.$client;

const getClient = () => {
  const client = globalThis.$client;
  if (!client) throw new Error("oRPC client not initialized");
  return client;
};

export const orpc = createTanstackQueryUtils(getClient());
