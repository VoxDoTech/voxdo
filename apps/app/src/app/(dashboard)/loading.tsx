export default function DashboardLoading() {
  return (
    <div className="flex flex-1 flex-col gap-4 p-4 md:gap-6 md:p-6">
      <div className="flex flex-wrap items-center gap-2">
        <div className="h-9 min-w-48 flex-1 animate-pulse rounded-md bg-muted" />
        <div className="h-9 w-44 animate-pulse rounded-md bg-muted" />
        <div className="h-9 w-24 animate-pulse rounded-md bg-muted" />
        <div className="h-9 w-28 animate-pulse rounded-md bg-muted" />
      </div>
      <ul className="grid gap-3">
        {Array.from({ length: 5 }).map((_, i) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton list
          <li key={i} className="h-20 animate-pulse rounded-xl border" />
        ))}
      </ul>
    </div>
  );
}
