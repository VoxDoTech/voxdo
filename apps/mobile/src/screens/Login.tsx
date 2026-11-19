import { useState } from "react";

import { Icon } from "../components/Icon";
import { signIn, signUp } from "../lib/api";

type Mode = "in" | "up";

function humanize(message: string): string {
  const normalized = message.toLowerCase();
  if (normalized.includes("invalid email or password")) {
    return "Неверный email или пароль";
  }
  if (normalized.includes("already exists")) {
    return "Этот email уже зарегистрирован";
  }
  if (normalized.includes("password")) {
    return "Пароль должен быть не короче 8 символов";
  }
  if (normalized.includes("invalid email")) {
    return "Проверьте адрес email";
  }
  return message;
}

export function LoginScreen({ onSignedIn }: { onSignedIn: () => void }) {
  const [mode, setMode] = useState<Mode>("in");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (busy) return;
    const trimmedEmail = email.trim();
    if (!trimmedEmail.includes("@")) {
      setError("Введите корректный email");
      return;
    }
    if (password.length < 8) {
      setError("Пароль должен быть не короче 8 символов");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result =
        mode === "in"
          ? await signIn(trimmedEmail, password)
          : await signUp(
              trimmedEmail,
              password,
              name.trim() || trimmedEmail.split("@")[0] || "Друг",
            );
      if (result.ok) {
        onSignedIn();
      } else {
        setError(humanize(result.error ?? "Не удалось выполнить вход"));
      }
    } catch {
      setError("Нет соединения с сервером. Проверьте интернет.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-screen">
      <div className="login-hero">
        <div className="login-orb">
          <span className="login-ring" />
          <span className="login-ring delay" />
          <Icon name="wave" size={40} strokeWidth={1.7} />
        </div>
        <h1>VoxDo</h1>
        <p>
          Говорите — мы запишем, расшифруем
          <br />и превратим речь в заметки.
        </p>
      </div>

      <div className="login-card">
        <div className="segmented auth-tabs">
          <button
            type="button"
            className={mode === "in" ? "segment active" : "segment"}
            onClick={() => {
              setMode("in");
              setError(null);
            }}
          >
            Вход
          </button>
          <button
            type="button"
            className={mode === "up" ? "segment active" : "segment"}
            onClick={() => {
              setMode("up");
              setError(null);
            }}
          >
            Регистрация
          </button>
        </div>

        {mode === "up" && (
          <div className="input-with-icon">
            <Icon name="user" size={18} />
            <input
              placeholder="Как вас зовут"
              value={name}
              onChange={(event) => setName(event.target.value)}
              autoComplete="name"
            />
          </div>
        )}

        <div className="input-with-icon">
          <Icon name="mail" size={18} />
          <input
            placeholder="Email"
            type="email"
            inputMode="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
            autoCapitalize="none"
            spellCheck={false}
            onKeyDown={(event) => {
              if (event.key === "Enter") void submit();
            }}
          />
        </div>

        <div className="input-with-icon">
          <Icon name="lock" size={18} />
          <input
            placeholder="Пароль"
            type={showPassword ? "text" : "password"}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete={mode === "in" ? "current-password" : "new-password"}
            onKeyDown={(event) => {
              if (event.key === "Enter") void submit();
            }}
          />
          <button
            type="button"
            className="input-addon"
            onClick={() => setShowPassword((value) => !value)}
            aria-label={showPassword ? "Скрыть пароль" : "Показать пароль"}
          >
            <Icon name={showPassword ? "eyeOff" : "eye"} size={17} />
          </button>
        </div>

        {error && (
          <div className="auth-error" role="alert">
            <Icon name="alert" size={16} />
            <span>{error}</span>
          </div>
        )}

        <button
          type="button"
          className="btn btn-primary btn-large"
          disabled={busy || !email || !password}
          onClick={() => void submit()}
        >
          {busy ? (
            <span className="spinner-ring light small" />
          ) : mode === "in" ? (
            "Войти"
          ) : (
            "Создать аккаунт"
          )}
        </button>

        <p className="login-fineprint">
          {mode === "in"
            ? "Нет аккаунта? Нажмите «Регистрация» выше."
            : "Пароль не короче 8 символов. Данные защищены."}
        </p>
      </div>
    </div>
  );
}
