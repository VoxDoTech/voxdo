import type { RouterOutputs } from "@acme/api";
import { useCallback, useEffect, useRef, useState } from "react";

import { API_URL, fetchSession, type SessionUser, signOut } from "./lib/api";
import { LoginScreen } from "./screens/Login";
import { NoteDetailScreen } from "./screens/NoteDetail";
import { NotesScreen } from "./screens/Notes";
import { RecordScreen } from "./screens/Record";

type Tab = "notes" | "record";
export type Note = RouterOutputs["note"]["list"][number];
export type Folder = RouterOutputs["folder"]["list"][number];

interface DetailState {
  note: Note;
}

export function App() {
  const [user, setUser] = useState<SessionUser | null | undefined>(undefined);
  const [sessionError, setSessionError] = useState(false);
  const [tab, setTab] = useState<Tab>("notes");
  const [detail, setDetail] = useState<DetailState | null>(null);
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

  // A different signed-in user (sign-out, account switch) must not see the
  // previous user's open note or navigation state.
  useEffect(() => {
    const id = user?.id ?? null;
    if (lastUserId.current !== undefined && id !== lastUserId.current) {
      setDetail(null);
      setTab("notes");
    }
    lastUserId.current = id;
  }, [user]);

  if (user === undefined) {
    if (sessionError) {
      return (
        <div className="splash">
          <p>Нет соединения с сервером</p>
          <button
            type="button"
            className="primary"
            onClick={() => {
              setUser(undefined);
              void refreshSession();
            }}
          >
            Повторить
          </button>
        </div>
      );
    }
    return <div className="splash">VoxDo</div>;
  }
  if (!user) {
    return <LoginScreen onSignedIn={refreshSession} />;
  }
  if (!API_URL) {
    return (
      <div className="splash">
        <p>Set VITE_API_URL in apps/mobile/.env</p>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">VoxDo</span>
        <div className="topbar-right">
          <span className="user-email">{user.email}</span>
          <button
            type="button"
            className="ghost"
            onClick={() => {
              void signOut().then(refreshSession);
            }}
          >
            Выйти
          </button>
        </div>
      </header>

      <main className="content">
        {detail ? (
          <NoteDetailScreen
            note={detail.note}
            onBack={() => setDetail(null)}
            onDeleted={() => {
              setDetail(null);
              setTab("notes");
            }}
          />
        ) : tab === "notes" ? (
          <NotesScreen onOpen={(note) => setDetail({ note })} />
        ) : (
          <RecordScreen
            onSaved={() => {
              setTab("notes");
            }}
          />
        )}
      </main>

      {!detail && (
        <nav className="tabbar">
          <button
            type="button"
            className={tab === "notes" ? "tab active" : "tab"}
            onClick={() => setTab("notes")}
          >
            Заметки
          </button>
          <button
            type="button"
            className={tab === "record" ? "tab record-tab" : "tab record-tab"}
            onClick={() => setTab("record")}
          >
            ● Записать
          </button>
        </nav>
      )}
    </div>
  );
}
