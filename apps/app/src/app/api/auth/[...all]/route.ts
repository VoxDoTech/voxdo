import { auth } from "~/auth/server";
import { handleCorsPreflight, withCors } from "~/lib/cors";

async function handle(request: Request) {
  const preflight = handleCorsPreflight(request);
  if (preflight) return preflight;
  return withCors(request, await auth.handler(request));
}

export const GET = handle;
export const POST = handle;
export const OPTIONS = handle;
