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
  getAccessToken,
  setAccessToken
} from "../api/client";

interface AuthIdentity {
  subject: string;
  roles: string[];
  permissions: string[];
  actor_type: string;
}

interface AuthState {
  token: string;
  permissions: string[];
  authenticated: boolean;
  loading: boolean;
  login: (token: string) => void;
  logout: () => void;
  can: (permission: string) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState(getAccessToken());
  const [identity, setIdentity] = useState<AuthIdentity | null>(null);
  const [loading, setLoading] = useState(Boolean(token));
  const permissions = useMemo(() => identity?.permissions ?? [], [identity]);
  const login = useCallback((value: string) => {
    setAccessToken(value);
    setLoading(true);
    setToken(getAccessToken());
  }, []);
  const logout = useCallback(() => {
    setAccessToken("");
    setToken("");
    setIdentity(null);
    setLoading(false);
  }, []);
  useEffect(() => {
    if (!token) {
      setIdentity(null);
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    api<AuthIdentity>("/auth/me")
      .then((value) => {
        if (active) setIdentity(value);
      })
      .catch(() => {
        if (active) logout();
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [logout, token]);
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
        token,
        permissions,
        authenticated: Boolean(token && identity),
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
