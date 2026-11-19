/** Russian date/duration formatting shared by the mobile screens. */

const dayFmt = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "long",
});

const timeFmt = new Intl.DateTimeFormat("ru-RU", {
  hour: "2-digit",
  minute: "2-digit",
});

const weekdayFmt = new Intl.DateTimeFormat("ru-RU", {
  weekday: "long",
});

const fullFmt = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "long",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

function formatTime(iso: string | Date): string {
  return timeFmt.format(new Date(iso));
}

export function formatFull(iso: string | Date): string {
  return fullFmt.format(new Date(iso));
}

/** Short relative label: "14:32" today, "вчера", "12 нояб.". */
export function formatRelative(iso: string | Date): string {
  const date = new Date(iso);
  const now = new Date();
  const diffDays = Math.round(
    (startOfDay(now).getTime() - startOfDay(date).getTime()) / 86_400_000,
  );
  if (diffDays === 0) return formatTime(date);
  if (diffDays === 1) return "вчера";
  if (diffDays < 7) return weekdayFmt.format(date);
  return dayFmt.format(date);
}

/** Groups notes under "Сегодня", "Вчера", "12 ноября" headers. */
export function dayLabel(iso: string | Date): string {
  const date = new Date(iso);
  const now = new Date();
  const diffDays = Math.round(
    (startOfDay(now).getTime() - startOfDay(date).getTime()) / 86_400_000,
  );
  if (diffDays === 0) return "Сегодня";
  if (diffDays === 1) return "Вчера";
  if (diffDays > 1 && diffDays < 7) {
    const label = weekdayFmt.format(date);
    return label.charAt(0).toUpperCase() + label.slice(1);
  }
  return dayFmt.format(date);
}

export function dayKey(iso: string | Date): string {
  return startOfDay(new Date(iso)).toISOString();
}

function startOfDay(date: Date): Date {
  const copy = new Date(date);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

/** `0:42` / `12:05` — for clips and the record timer. */
export function formatClock(totalSeconds: number): string {
  const safe = Math.max(0, Math.round(totalSeconds));
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export function noteTitle(note: { title: string | null; content: string }) {
  const title = note.title?.trim();
  if (title) return title;
  const firstLine = note.content.trim().split("\n")[0] ?? "";
  if (firstLine) {
    return firstLine.length > 64 ? `${firstLine.slice(0, 64)}…` : firstLine;
  }
  return "Без названия";
}

export function wordCount(text: string): number {
  const trimmed = text.trim();
  return trimmed ? trimmed.split(/\s+/).length : 0;
}

export function initials(name?: string | null, email?: string): string {
  const source = name?.trim();
  if (source) {
    return source
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part.charAt(0).toUpperCase())
      .join("");
  }
  return (email?.charAt(0) ?? "V").toUpperCase();
}
