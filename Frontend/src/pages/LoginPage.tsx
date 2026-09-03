import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

type LoginPageProps = {
  theme: "night" | "day";
  onToggleTheme: () => void;
};

type GooglePromptNotification = {
  isNotDisplayed: () => boolean;
  isSkippedMoment: () => boolean;
  isDismissedMoment: () => boolean;
  getNotDisplayedReason?: () => string;
  getSkippedReason?: () => string;
  getDismissedReason?: () => string;
};

type GoogleCredentialResponse = {
  credential: string;
};

type GoogleIdentityClient = {
  initialize: (options: {
    client_id: string;
    callback: (response: GoogleCredentialResponse) => void;
    auto_select?: boolean;
    cancel_on_tap_outside?: boolean;
  }) => void;
  prompt: (listener?: (notification: GooglePromptNotification) => void) => void;
};

type GoogleNamespace = {
  accounts: {
    id: GoogleIdentityClient;
  };
};

declare global {
  interface Window {
    google?: GoogleNamespace;
    __stockassistantGoogleInitialized?: boolean;
    __stockassistantGoogleCredentialHandler?: (response: GoogleCredentialResponse) => void | Promise<void>;
  }
}

const GOOGLE_CLIENT_ID = (import.meta.env as Record<string, string | undefined>).VITE_GOOGLE_CLIENT_ID?.trim() || "";

export default function LoginPage({ theme, onToggleTheme }: LoginPageProps) {
  const { loginWithGoogleCredential, loginWithPasswordCredentials, user } = useAuth();
  const navigate = useNavigate();
  const loginWithGoogleCredentialRef = useRef(loginWithGoogleCredential);
  const [loadingScript, setLoadingScript] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [googleReady, setGoogleReady] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    loginWithGoogleCredentialRef.current = loginWithGoogleCredential;
  }, [loginWithGoogleCredential]);

  const clientMessage = useMemo(() => {
    if (!GOOGLE_CLIENT_ID) {
      return "Falta configurar VITE_GOOGLE_CLIENT_ID en el frontend.";
    }
    return "";
  }, []);

  useEffect(() => {
    if (user) {
      void navigate("/jupiter", { replace: true });
    }
  }, [navigate, user]);

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) {
      setLoadingScript(false);
      setError("Configura VITE_GOOGLE_CLIENT_ID para habilitar el login con Google.");
      return;
    }

    const existing = document.querySelector<HTMLScriptElement>('script[data-google-gsi="true"]');
    const script = existing ?? document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.dataset.googleGsi = "true";

    const initialize = () => {
      const client = window.google?.accounts.id;
      if (!client) {
        setLoadingScript(false);
        setError("Google Identity Services no se pudo cargar.");
        return;
      }

      window.__stockassistantGoogleCredentialHandler = async (response) => {
        if (!response?.credential) {
          setBusy(false);
          setError("Google no devolvio credencial. Intenta de nuevo.");
          return;
        }

        try {
          setBusy(true);
          setError("");
          await loginWithGoogleCredentialRef.current(response.credential);
          setBusy(false);
          void navigate("/jupiter", { replace: true });
        } catch (loginError) {
          setBusy(false);
          setError(loginError instanceof Error ? loginError.message : "No se pudo iniciar sesion con Google");
        }
      };

      if (!window.__stockassistantGoogleInitialized) {
        client.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: (response) => {
            void window.__stockassistantGoogleCredentialHandler?.(response);
          },
          auto_select: false,
          cancel_on_tap_outside: true,
        });
        window.__stockassistantGoogleInitialized = true;
      }

      setGoogleReady(true);
      setLoadingScript(false);
    };

    if (existing) {
      if (window.google?.accounts.id) {
        initialize();
      } else {
        existing.addEventListener("load", initialize, { once: true });
      }
      return;
    }

    script.addEventListener("load", initialize, { once: true });
    script.addEventListener(
      "error",
      () => {
        setLoadingScript(false);
        setError("No se pudo cargar el script de Google Identity Services.");
      },
      { once: true },
    );
    document.head.appendChild(script);
  }, [navigate]);

  const startGoogleFlow = () => {
    if (!googleReady || !window.google?.accounts.id) {
      setError(clientMessage || "Google aún no está listo.");
      return;
    }

    setError("");
    window.google.accounts.id.prompt();
  };

  const submitPasswordLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy || loadingScript) {
      return;
    }

    const normalizedEmail = email.trim().toLowerCase();
    if (!normalizedEmail || !password.trim()) {
      setError("Ingresa tu correo electrónico y tu contraseña.");
      return;
    }

    try {
      setBusy(true);
      setError("");
      await loginWithPasswordCredentials(normalizedEmail, password);
      setBusy(false);
      void navigate("/jupiter", { replace: true });
    } catch (loginError) {
      setBusy(false);
      setError(loginError instanceof Error ? loginError.message : "No se pudo iniciar sesion con email y contraseña");
    }
  };

  return (
    <main className="login-page">
      <section className="login-panel card">
        <div className="login-copy">
          <p className="brand-kicker">Master Pontia IA</p>
          <h1>Portal privado de Proyecto Jupiter</h1>
          <p className="login-lead">
            Accede con Google o con tus credenciales internas para validar tu identidad.
          </p>

          <div className="login-feature-list">
            <article>
              <span>01</span>
              <p>Google devuelve un ID token al frontend.</p>
            </article>
            <article>
              <span>02</span>
              <p>El backend verifica el token y sincroniza el usuario.</p>
            </article>
            <article>
              <span>03</span>
              <p>Se crea una sesión firmada para navegar el portal.</p>
            </article>
          </div>
        </div>

        <div className="login-card">
          <div className="login-card-top">
            <button className="theme-switch login-theme-switch" onClick={onToggleTheme} type="button">
              <span className="theme-switch-dot" aria-hidden="true" />
              {theme === "night" ? "Modo nocturno" : "Modo diurno"}
            </button>
          </div>

          <p className="section-label">Inicio de sesión</p>
          <h2>Continuar con Google</h2>
          <p className="muted">El acceso por usuario usa tu correo electrónico como identificador.</p>

          <form className="login-form stack" onSubmit={submitPasswordLogin}>
            <label className="stack">
              <span className="field-label">Correo electrónico</span>
              <input
                autoComplete="email"
                name="email"
                onChange={(event) => setEmail(event.target.value)}
                placeholder="tu@empresa.com"
                type="email"
                value={email}
              />
            </label>

            <label className="stack">
              <span className="field-label">Contraseña</span>
              <input
                autoComplete="current-password"
                name="password"
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Tu contraseña"
                type="password"
                value={password}
              />
            </label>

            <button
              className="primary-btn login-password-btn"
              disabled={busy || loadingScript || !email.trim() || !password.trim()}
              type="submit"
            >
              {busy ? "Validando..." : "Entrar con correo y contraseña"}
            </button>
          </form>

          <button
            className="primary-btn login-google-btn"
            disabled={busy || loadingScript || !GOOGLE_CLIENT_ID}
            onClick={startGoogleFlow}
            type="button"
          >
            {busy ? "Validando..." : "Continuar con Google"}
          </button>

          <p className="login-note">Si ya tienes cuenta, usa el correo registrado. Google sigue disponible como opción.</p>

          {clientMessage && <p className="error-line">{clientMessage}</p>}
          {error && <p className="error-line">{error}</p>}
          {!error && <p className="status-line">{loadingScript ? "Preparando login seguro..." : "Listo para autenticar."}</p>}
        </div>
      </section>
    </main>
  );
}
