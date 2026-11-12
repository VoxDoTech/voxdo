import { isAdmin } from "@acme/auth/roles";
import { Skeleton } from "@acme/ui";
import { Suspense } from "react";
import { getSession } from "~/auth/server";
import { AdminApp } from "~/components/admin/admin-app";
import { SiteHeader } from "~/components/layout";

export default function AdminPage() {
  return (
    <>
      <SiteHeader title="Администрирование" />
      <div className="flex flex-1 flex-col p-4 md:p-6">
        {/* The shell prerenders; the session check streams in. */}
        <Suspense fallback={<AdminSkeleton />}>
          <AdminGate />
        </Suspense>
      </div>
    </>
  );
}

async function AdminGate() {
  const session = await getSession();
  const user = session?.user;
  if (!user || !isAdmin({ email: user.email, role: user.role })) {
    return (
      <div className="text-muted-foreground rounded-xl border border-dashed p-10 text-center text-sm">
        Раздел доступен только администраторам.
      </div>
    );
  }
  return <AdminApp currentUserId={user.id} />;
}

function AdminSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton list
          <Skeleton key={i} className="h-24 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-96 w-full rounded-xl" />
    </div>
  );
}
