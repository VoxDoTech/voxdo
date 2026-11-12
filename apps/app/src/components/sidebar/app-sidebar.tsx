import { APP_CONFIG, paths } from "@acme/config";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@acme/ui";
import {
  IconInnerShadowTop,
  IconMicrophone,
  IconSettings,
  IconShield,
} from "@tabler/icons-react";
import type * as React from "react";
import { NavMain, NavSecondary, NavUser } from "~/components/sidebar";

export function AppSidebar({
  user,
  isAdmin = false,
  ...props
}: React.ComponentProps<typeof Sidebar> & {
  user: { name: string; email: string; avatar: string };
  isAdmin?: boolean;
}) {
  const navMain = [
    { title: "Заметки", url: paths.dashboard.root, icon: IconMicrophone },
    ...(isAdmin
      ? [
          {
            title: "Администрирование",
            url: paths.admin.root,
            icon: IconShield,
          },
        ]
      : []),
  ];

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              render={<a href={paths.dashboard.root} />}
            >
              <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                <IconInnerShadowTop className="size-4" />
              </div>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-semibold">
                  {APP_CONFIG.name}
                </span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={navMain} />
        <NavSecondary
          items={[
            {
              title: "Настройки",
              url: paths.settings.root,
              icon: IconSettings,
            },
          ]}
          className="mt-auto"
        />
      </SidebarContent>
      <SidebarFooter>
        <NavUser user={user} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
