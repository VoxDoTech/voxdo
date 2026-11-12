"use client";

import {
  Badge,
  Button,
  Input,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  toast,
} from "@acme/ui";
import { IconShield, IconUser, IconUsers } from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useEffect, useState } from "react";
import { authClient } from "~/auth/client";
import { formatNoteDate } from "~/lib/format";
import { orpc } from "~/orpc/react";

const PAGE_SIZE = 50;

function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

export function AdminApp({ currentUserId }: { currentUserId: string }) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search).trim();

  const statsQuery = useQuery(orpc.admin.stats.overview.queryOptions());

  const listQuery = useQuery({
    ...orpc.admin.users.list.queryOptions({
      input: { limit: PAGE_SIZE, offset: 0 },
    }),
    enabled: debouncedSearch.length === 0,
  });
  const searchQuery = useQuery({
    ...orpc.admin.users.search.queryOptions({
      input: { query: debouncedSearch, limit: PAGE_SIZE },
    }),
    enabled: debouncedSearch.length > 0,
  });
  const users = debouncedSearch ? searchQuery.data : listQuery.data;
  const usersQuery = debouncedSearch ? searchQuery : listQuery;

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: orpc.admin.key() });

  const setRole = useMutation({
    mutationFn: async ({
      userId,
      role,
    }: {
      userId: string;
      role: "admin" | "user";
    }) => {
      const { error } = await authClient.admin.setRole({ userId, role });
      if (error) throw new Error(error.message ?? "Не удалось изменить роль");
    },
    onSuccess: refresh,
    onError: (err) => toast.error(err.message),
  });

  const banUser = useMutation({
    mutationFn: async ({
      userId,
      unban,
    }: {
      userId: string;
      unban: boolean;
    }) => {
      const { error } = unban
        ? await authClient.admin.unbanUser({ userId })
        : await authClient.admin.banUser({
            userId,
            banReason: "Заблокирован администратором",
          });
      if (error) throw new Error(error.message ?? "Не удалось изменить статус");
    },
    onSuccess: refresh,
    onError: (err) => toast.error(err.message),
  });

  const stats = statsQuery.data;

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          icon={<IconUsers className="size-4" />}
          label="Пользователи"
          value={stats?.users}
        />
        <StatCard
          icon={<IconUser className="size-4" />}
          label="Заметки"
          value={stats?.notes}
        />
        <StatCard
          icon={<IconShield className="size-4" />}
          label="Папки"
          value={stats?.folders}
        />
      </div>

      <div className="flex items-center gap-2">
        <Input
          placeholder="Поиск по имени или email…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-sm"
        />
      </div>

      <div className="rounded-xl border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Пользователь</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Роль</TableHead>
              <TableHead>Статус</TableHead>
              <TableHead>Регистрация</TableHead>
              <TableHead className="text-right">Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {usersQuery.isPending ? (
              <TableRow>
                <TableCell colSpan={6}>
                  <Skeleton className="h-8 w-full" />
                </TableCell>
              </TableRow>
            ) : usersQuery.isError ? (
              <TableRow>
                <TableCell colSpan={6} className="text-destructive">
                  Не удалось загрузить пользователей.
                </TableCell>
              </TableRow>
            ) : !users || users.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={6}
                  className="text-muted-foreground text-center"
                >
                  {debouncedSearch
                    ? "Никого не найдено."
                    : "Пользователей пока нет."}
                </TableCell>
              </TableRow>
            ) : (
              users.map((u) => {
                const isSelf = u.id === currentUserId;
                const isAdminUser = u.role
                  ?.split(",")
                  .some((r) => r.trim() === "admin");
                return (
                  <TableRow key={u.id}>
                    <TableCell className="font-medium">
                      {u.name}
                      {u.username && (
                        <span className="text-muted-foreground ml-1 text-xs">
                          @{u.username}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {u.email}
                    </TableCell>
                    <TableCell>
                      {isAdminUser ? (
                        <Badge>admin</Badge>
                      ) : (
                        <Badge variant="secondary">user</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      {u.banned ? (
                        <Badge variant="destructive">заблокирован</Badge>
                      ) : u.emailVerified ? (
                        <Badge variant="secondary">подтверждён</Badge>
                      ) : (
                        <Badge variant="outline">не подтверждён</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {formatNoteDate(u.createdAt)}
                    </TableCell>
                    <TableCell className="text-right">
                      {!isSelf && (
                        <div className="flex justify-end gap-1">
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={setRole.isPending || banUser.isPending}
                            onClick={() =>
                              setRole.mutate({
                                userId: u.id,
                                role: isAdminUser ? "user" : "admin",
                              })
                            }
                          >
                            {isAdminUser ? "Снять админа" : "Сделать админом"}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={setRole.isPending || banUser.isPending}
                            onClick={() =>
                              banUser.mutate({
                                userId: u.id,
                                unban: !!u.banned,
                              })
                            }
                          >
                            {u.banned ? "Разблокировать" : "Заблокировать"}
                          </Button>
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: number | undefined;
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl border p-4">
      <div className="bg-muted flex size-9 items-center justify-center rounded-lg">
        {icon}
      </div>
      <div>
        <div className="text-2xl font-semibold">
          {value ?? <Skeleton className="h-7 w-10" />}
        </div>
        <div className="text-muted-foreground text-sm">{label}</div>
      </div>
    </div>
  );
}
