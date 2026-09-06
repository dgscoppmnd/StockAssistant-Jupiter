import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import {
  clearSessionToken,
  getSessionExpiryEpoch,
  fetchCurrentSession,
  getSessionToken,
  loginWithGoogle,
  loginWithPassword,
  logoutSession,
  setSessionToken,
} from "./api";
import type { AuthUser } from "./types";

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  sessionExpiresAt: number | null;
  sessionRemainingSeconds: number;
  loginWithGoogleCredential: (credential: string) => Promise<AuthUser>;
  loginWithPasswordCredentials: (email: string, password: string) => Promise<AuthUser>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [sessionExpiresAt, setSessionExpiresAt] = useState<number | null>(null);
  const [sessionRemainingSeconds, setSessionRemainingSeconds] = useState(0);

  useEffect(() => {
    if (!sessionExpiresAt) {
      setSessionRemainingSeconds(0);
      return;
    }

    const tick = () => {
      const remaining = Math.max(sessionExpiresAt - Math.floor(Date.now() / 1000), 0);
      setSessionRemainingSeconds(remaining);
      if (remaining <= 0) {
        clearSessionToken();
        setUser(null);
        setSessionExpiresAt(null);
      }
    };

    tick();
    const timerId = window.setInterval(tick, 1000);
    return () => window.clearInterval(timerId);
  }, [sessionExpiresAt]);

  const refreshSession = async () => {
    const token = getSessionToken();
    if (!token) {
      setUser(null);
      setSessionExpiresAt(null);
      return;
    }

    setSessionExpiresAt(getSessionExpiryEpoch(token));

    try {
      const currentUser = await fetchCurrentSession();
      setUser(currentUser);
    } catch {
      clearSessionToken();
      setUser(null);
      setSessionExpiresAt(null);
    }
  };

  useEffect(() => {
    let alive = true;

    const bootstrap = async () => {
      const token = getSessionToken();
      if (!token) {
        if (alive) {
          setLoading(false);
        }
        return;
      }

      if (alive) {
        setSessionExpiresAt(getSessionExpiryEpoch(token));
      }

      try {
        const currentUser = await fetchCurrentSession();
        if (alive) {
          setUser(currentUser);
        }
      } catch {
        clearSessionToken();
        if (alive) {
          setUser(null);
          setSessionExpiresAt(null);
        }
      } finally {
        if (alive) {
          setLoading(false);
        }
      }
    };

    void bootstrap();

    return () => {
      alive = false;
    };
  }, []);

  const loginWithGoogleCredential = async (credential: string) => {
    const session = await loginWithGoogle(credential);
    setSessionToken(session.access_token);
    setSessionExpiresAt(getSessionExpiryEpoch(session.access_token));
    setUser(session.user);
    return session.user;
  };

  const loginWithPasswordCredentials = async (email: string, password: string) => {
    const session = await loginWithPassword(email, password);
    setSessionToken(session.access_token);
    setSessionExpiresAt(getSessionExpiryEpoch(session.access_token));
    setUser(session.user);
    return session.user;
  };

  const logout = async () => {
    await logoutSession();
    setUser(null);
    setSessionExpiresAt(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        sessionExpiresAt,
        sessionRemainingSeconds,
        loginWithGoogleCredential,
        loginWithPasswordCredentials,
        logout,
        refreshSession,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}