import { useState } from "react";

import { signIn, signUp } from "../lib/api";

export function LoginScreen({ onSignedIn }: { onSignedIn: () => void }) {
  const [mode, setMode] = useState<"in" | "up">("in");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const res =
        mode === "in"
          ? await signIn(email.trim(), password)
          : await signUp(email.trim(), password, name.trim() || email.trim());
      if (res.ok) {
        onSignedIn();
      } else {
        setError(res.error ?? "Не удалось войти");
      }
    } catch {
      setError("Нет соединения с сервером");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login">
      <h1>VoxDo</h1>
      <p className="muted">Голосовые заметки — говори, приложение запомнит</p>

      {mode === "up" && (
        <input
          placeholder="Имя"
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoComplete="name"
        />
      )}
      <input
        placeholder="Email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        autoComplete="email"
      />
      <input
        placeholder="Пароль"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        autoComplete={mode === "in" ? "current-password" : "new-password"}
        onKeyDown={(e) => {
          if (e.key === "Enter") void submit();
        }}
      />

      {error && <p className="error">{error}</p>}

      <button
        type="button"
        className="primary"
        disabled={busy || !email || !password}
        onClick={() => void submit()}
      >
        {busy ? "…" : mode === "in" ? "Войти" : "Создать аккаунт"}
      </button>

      <button
        type="button"
        className="link"
        onClick={() => setMode(mode === "in" ? "up" : "in")}
      >
        {mode === "in" ? "Нет аккаунта? Регистрация" : "Уже есть аккаунт? Вход"}
      </button>
    </div>
  );
}
