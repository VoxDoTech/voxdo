import type { RouterOutputs } from "@acme/api";
import { useEffect, useState } from "react";
import type { Note } from "../App";
import { Icon, type IconName } from "../components/Icon";
import { useToast } from "../components/Toast";
import type { SessionUser } from "../lib/api";
import { api, signOut } from "../lib/api";
import { fetchAllNotes, ShareActivationError, shareNotes } from "../lib/export";
import { initials } from "../lib/format";
import type { ThemeMode } from "../lib/theme";

type Stats = RouterOutputs["note"]["stats"];

interface Props {
  user: SessionUser;
  themeMode: ThemeMode;
  onThemeChange: (mode: ThemeMode) => void;
  onSignedOut: () => void;
}

const themeOptions: { value: ThemeMode; label: string; icon: IconName }[] = [
  { value: "system", label: "Система", icon: "monitor" },
  { value: "light", label: "Светлая", icon: "sun" },
  { value: "dark", label: "Тёмная", icon: "moon" },
];

export function ProfileScreen({
  user,
  themeMode,
  onThemeChange,
  onSignedOut,
}: Props) {
  const toast = useToast();
  const [stats, setStats] = useState<Stats | null>(null);
  const [loadingStats, setLoadingStats] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [pendingNotes, setPendingNotes] = useState<Note[] | null>(null);
  const [signingOut, setSigningOut] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);

  // biome-ignore lint/correctness/useExhaustiveDependencies: reloadToken is a deliberate refetch trigger
  useEffect(() => {
    let active = true;
    setLoadingStats(true);
    api.note
      .stats()
      .then((result) => {
        if (active) setStats(result);
      })
      .catch(() => {
        if (active) toast.show("Не удалось загрузить статистику", "error");
      })
      .finally(() => {
        if (active) setLoadingStats(false);
      });
    return () => {
      active = false;
    };
  }, [reloadToken, toast]);

  const exportNotes = async () => {
    if (exporting) return;
    setExporting(true);
    let notes = pendingNotes;
    try {
      notes ??= await fetchAllNotes();
      if (notes.length === 0) {
        toast.show("Пока нечего экспортировать", "info");
        return;
      }
      const result = await shareNotes(notes);
      setPendingNotes(null);
      toast.show(
        result === "shared"
          ? "Экспорт готов"
          : result === "copied"
            ? "Заметки скопированы в буфер обмена"
            : "Файл сохранён",
        "success",
      );
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === "AbortError") return;
      if (cause instanceof ShareActivationError && notes) {
        // The fetch outlived the tap's activation window: keep the loaded
        // notes and let the next tap share them straight away.
        setPendingNotes(notes);
        toast.show("Файл готов — нажмите «Поделиться» ещё раз", "info");
        return;
      }
      toast.show("Не удалось экспортировать заметки", "error");
    } finally {
      setExporting(false);
    }
  };

  const doSignOut = async () => {
    if (signingOut) return;
    setSigningOut(true);
    try {
      await signOut();
      onSignedOut();
    } finally {
      setSigningOut(false);
    }
  };

  const minutes = stats ? Math.round(stats.audioSeconds / 60) : null;
  const minutesLabel =
    minutes === null
      ? "—"
      : minutes === 0 && (stats?.audioSeconds ?? 0) > 0
        ? "<1"
        : String(minutes);

  return (
    <div className="screen">
      <div className="screen-scroll">
        <div className="screen-head">
          <div>
            <p className="eyebrow">Аккаунт</p>
            <h1>Профиль</h1>
          </div>
          <button
            type="button"
            className="btn-icon"
            onClick={() => setReloadToken((value) => value + 1)}
            aria-label="Обновить статистику"
          >
            <Icon name="refresh" size={18} />
          </button>
        </div>

        <div className="profile-hero">
          <div className="avatar big">{initials(user.name, user.email)}</div>
          <div className="profile-identity">
            <strong>{user.name || "Без имени"}</strong>
            <span>{user.email}</span>
          </div>
          <span className="profile-badge">
            <Icon name="sparkles" size={13} />
            VoxDo
          </span>
        </div>

        <div className="stats-grid">
          <StatCard
            icon="file"
            label="Заметок"
            value={stats ? String(stats.notes) : "—"}
            loading={loadingStats}
          />
          <StatCard
            icon="mic"
            label="Голосовых"
            value={stats ? String(stats.voice) : "—"}
            loading={loadingStats}
          />
          <StatCard
            icon="clock"
            label="Минут записи"
            value={minutesLabel}
            loading={loadingStats}
          />
          <StatCard
            icon="folder"
            label="Папок"
            value={stats ? String(stats.folders) : "—"}
            loading={loadingStats}
          />
        </div>

        {stats && stats.processing > 0 && (
          <div className="processing-note">
            <span className="dot-pulse" />
            Расшифровывается заметок: {stats.processing}
          </div>
        )}

        <section className="card-section">
          <h2>Оформление</h2>
          <div className="segmented">
            {themeOptions.map((option) => (
              <button
                type="button"
                key={option.value}
                className={
                  themeMode === option.value ? "segment active" : "segment"
                }
                onClick={() => onThemeChange(option.value)}
                aria-pressed={themeMode === option.value}
              >
                <Icon name={option.icon} size={16} />
                {option.label}
              </button>
            ))}
          </div>
          <p className="section-hint">
            Тёмная тема экономит батарею на OLED-экранах.
          </p>
        </section>

        <section className="card-section">
          <h2>Данные</h2>
          <button
            type="button"
            className="row-action"
            onClick={() => void exportNotes()}
            disabled={exporting}
          >
            <span className="row-action-icon">
              {exporting ? (
                <span className="spinner-ring small" />
              ) : (
                <Icon name={pendingNotes ? "share" : "download"} size={18} />
              )}
            </span>
            <span className="row-action-text">
              <strong>
                {exporting
                  ? "Готовим экспорт…"
                  : pendingNotes
                    ? "Поделиться файлом"
                    : "Экспорт заметок"}
              </strong>
              <span>
                {pendingNotes
                  ? "Файл готов — нажмите, чтобы поделиться"
                  : "Markdown-файл со всеми записями"}
              </span>
            </span>
            <Icon name="chevronRight" size={16} />
          </button>
        </section>

        <button
          type="button"
          className="btn btn-ghost logout-btn"
          onClick={() => void doSignOut()}
          disabled={signingOut}
        >
          <Icon name="logout" size={17} />
          {signingOut ? "Выходим…" : "Выйти из аккаунта"}
        </button>

        <p className="app-version">VoxDo · голосовые заметки · 0.1.0</p>
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  loading,
}: {
  icon: IconName;
  label: string;
  value: string;
  loading: boolean;
}) {
  return (
    <div className="stat-card">
      <span className="stat-icon">
        <Icon name={icon} size={17} />
      </span>
      <span className={loading ? "stat-value loading" : "stat-value"}>
        {value}
      </span>
      <span className="stat-label">{label}</span>
    </div>
  );
}
