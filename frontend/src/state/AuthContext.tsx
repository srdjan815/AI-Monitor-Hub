import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode
} from "react";
import {
  decodeTokenPermissions,
  getAccessToken,
  setAccessToken
} from "../api/client";

interface AuthState {
  token: string;
  permissions: string[];
  authenticated: boolean;
  login: (token: string) => void;
  logout: () => void;
  can: (permission: string) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState(getAccessToken());
  const permissions = useMemo(() => decodeTokenPermissions(token), [token]);
  const login = useCallback((value: string) => {
    setAccessToken(value);
    setToken(getAccessToken());
  }, []);
  const logout = useCallback(() => {
    setAccessToken("");
    setToken("");
  }, []);
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
        authenticated: Boolean(token),
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
