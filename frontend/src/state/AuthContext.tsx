import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode
} from "react";
import {
  AUTHENTICATION_FAILED_EVENT,
  api,
  createSession,
  deleteSession
} from "../api/client";

interface AuthIdentity {
  subject: string;
  roles: string[];
  permissions: string[];
  actor_type: string;
}

interface AuthState {
  permissions: string[];
  authenticated: boolean;
  loading: boolean;
  login: (token: string) => Promise<void>;
  logout: () => Promise<void>;
  can: (permission: string) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [identity, setIdentity] = useState<AuthIdentity | null>(null);
  const [loading, setLoading] = useState(true);
  const permissions = useMemo(() => identity?.permissions ?? [], [identity]);
  const refreshIdentity = useCallback(async () => {
    setLoading(true);
    try {
      setIdentity(await api<AuthIdentity>("/auth/me"));
    } finally {
      setLoading(false);
    }
  }, []);
  const login = useCallback(async (value: string) => {
    await createSession(value);
    await refreshIdentity();
  }, [refreshIdentity]);
  const logout = useCallback(async () => {
    try { await deleteSession(); } catch { /* lokalno odjavljivanje mora uspeti */ }
    setIdentity(null);
    setLoading(false);
  }, []);
  useEffect(() => {
    let active = true;
    api<AuthIdentity>("/auth/me")
      .then((value) => {
        if (active) setIdentity(value);
      })
      .catch(() => {
        if (active) setIdentity(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    window.addEventListener(AUTHENTICATION_FAILED_EVENT, logout);
    return () => window.removeEventListener(AUTHENTICATION_FAILED_EVENT, logout);
  }, [logout]);
  const can = useCallback(
    (permission: string) =>
      permissions.includes(permission) || permissions.includes("*"),
    [permissions]
  );
  return (
    <AuthContext.Provider
      value={{
        permissions,
        authenticated: Boolean(identity),
        loading,
        login,
        logout,
        can
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const value = useContext(AuthContext);
  if (!value) throw new Error("AuthProvider nedostaje");
  return value;
}
