import type { RouterOutputs } from "@acme/api";
import { useCallback, useEffect, useRef, useState } from "react";

import { Icon } from "./components/Icon";
import { ToastProvider } from "./components/Toast";
import { API_URL, fetchSession, type SessionUser } from "./lib/api";
import { initials } from "./lib/format";
import { applyTheme, readTheme, storeTheme, type ThemeMode } from "./lib/theme";
import { LoginScreen } from "./screens/Login";
import { NoteDetailScreen } from "./screens/NoteDetail";
import { NotesScreen } from "./screens/Notes";
import { ProfileScreen } from "./screens/Profile";
import { RecordScreen } from "./screens/Record";

type Tab = "notes" | "record" | "profile";
export type Note = RouterOutputs["note"]["list"][number];
export type Folder = RouterOutputs["folder"]["list"][number];

export function App() {
  return (
    <ToastProvider>
      <Root />
    </ToastProvider>
  );
}

function Root() {
  const [user, setUser] = useState<SessionUser | null | undefined>(undefined);
  const [sessionError, setSessionError] = useState(false);
  const [tab, setTab] = useState<Tab>("notes");
  const [detail, setDetail] = useState<Note | null>(null);
  const [notesVersion, setNotesVersion] = useState(0);
  const [themeMode, setThemeMode] = useState<ThemeMode>(readTheme);
  const lastUserId = useRef<string | null | undefined>(undefined);

  const refreshSession = useCallback(async () => {
    try {
      setUser(await fetchSession());
      setSessionError(false);
    } catch {
      setSessionError(true);
    }
  }, []);

  useEffect(() => {
    void refreshSession();
  }, [refreshSession]);

  useEffect(() => {
    applyTheme(themeMode);
    storeTheme(themeMode);
    if (themeMode !== "system") return;
    const media = window.matchMedia("(prefers-color-scheme: light)");
    const onChange = () => applyTheme("system");
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [themeMode]);

  // A different signed-in user must never see the previous session's state.
  useEffect(() => {
    const id = user?.id ?? null;
    if (lastUserId.current !== undefined && id !== lastUserId.current) {
      setDetail(null);
      setTab("notes");
    }
    lastUserId.current = id;
  }, [user]);

  if (user === undefined) {
    return sessionError ? (
      <div className="splash">
        <div className="splash-error">
          <Icon name="alert" size={26} />
        </div>
        <h1>Нет связи с сервером</h1>
        <p>Проверьте интернет и попробуйте снова.</p>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => {
            setSessionError(false);
            void refreshSession();
          }}
        >
          Повторить
        </button>
      </div>
    ) : (
      <div className="splash">
        <div className="splash-mark">
          <span className="splash-ring" />
          <Icon name="wave" size={30} strokeWidth={1.7} />
        </div>
        <h1>VoxDo</h1>
        <p>Ваши мысли, вслух</p>
        <span className="splash-dots" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
      </div>
    );
  }

  if (!user) return <LoginScreen onSignedIn={refreshSession} />;

  if (!API_URL) {
    return (
      <div className="splash">
        <h1>Нужна настройка</h1>
        <p>Укажите VITE_API_URL в apps/mobile/.env</p>
      </div>
    );
  }

  const openNote = (note: Note) => setDetail(note);

  const closeDetail = () => {
    setDetail(null);
    setNotesVersion((value) => value + 1);
  };

  return (
    <div className="app">
      {tab !== "record" && (
        <header className="appbar">
          <div className="brand">
            <span className="brand-mark">
              <Icon name="wave" size={16} strokeWidth={2} />
            </span>
            <span className="brand-name">VoxDo</span>
          </div>
          <div className="appbar-right">
            <span className="appbar-email">{user.email}</span>
            <button
              type="button"
              className={tab === "profile" ? "avatar active" : "avatar"}
              onClick={() => setTab("profile")}
              aria-label="Открыть профиль"
            >
              {initials(user.name, user.email)}
            </button>
          </div>
        </header>
      )}

      <main className={`app-main${tab === "record" ? " immersive" : ""}`}>
        {tab === "notes" && (
          <NotesScreen
            reloadKey={notesVersion}
            onOpen={openNote}
            onRecord={() => setTab("record")}
          />
        )}
        {tab === "record" && (
          <RecordScreen
            onSaved={(note) => {
              setNotesVersion((value) => value + 1);
              setDetail(note);
              setTab("notes");
            }}
          />
        )}
        {tab === "profile" && (
          <ProfileScreen
            user={user}
            themeMode={themeMode}
            onThemeChange={setThemeMode}
            onSignedOut={refreshSession}
          />
        )}
      </main>

      <nav className="dock" aria-label="Основная навигация">
        <button
          type="button"
          className={tab === "notes" ? "dock-item active" : "dock-item"}
          onClick={() => setTab("notes")}
          aria-current={tab === "notes" ? "page" : undefined}
        >
          <Icon name="file" size={20} />
          <span>Заметки</span>
        </button>
        <button
          type="button"
          className={
            tab === "record" ? "dock-item record active" : "dock-item record"
          }
          onClick={() => setTab("record")}
          aria-current={tab === "record" ? "page" : undefined}
          aria-label="Записать голосовую заметку"
        >
          <span className="dock-record">
            <Icon name="mic" size={24} strokeWidth={1.9} />
          </span>
          <span>Записать</span>
        </button>
        <button
          type="button"
          className={tab === "profile" ? "dock-item active" : "dock-item"}
          onClick={() => setTab("profile")}
          aria-current={tab === "profile" ? "page" : undefined}
        >
          <Icon name="user" size={20} />
          <span>Профиль</span>
        </button>
      </nav>

      {detail && (
        <NoteDetailScreen
          note={detail}
          onBack={closeDetail}
          onDeleted={() => {
            setDetail(null);
            setTab("notes");
            setNotesVersion((value) => value + 1);
          }}
        />
      )}
    </div>
  );
}
