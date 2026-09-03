import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode
} from "react";
import { useMediaQuery } from "@mui/material";

export type ThemePreference = "light" | "dark" | "system";
export type Density = "compact" | "standard" | "comfortable";

interface Preferences {
  theme: ThemePreference;
  resolvedTheme: "light" | "dark";
  setTheme: (value: ThemePreference) => void;
  navigationCollapsed: boolean;
  setNavigationCollapsed: (value: boolean) => void;
  density: Density;
  setDensity: (value: Density) => void;
}

const PreferencesContext = createContext<Preferences | null>(null);

function storedTheme(): ThemePreference {
  const value = localStorage.getItem("amh.theme");
  return value === "light" || value === "dark" || value === "system"
    ? value
    : "system";
}

export function PreferencesProvider({ children }: { children: ReactNode }) {
  const systemDark = useMediaQuery("(prefers-color-scheme: dark)");
  const [theme, setThemeState] = useState<ThemePreference>(storedTheme);
  const [navigationCollapsed, setNavigationCollapsed] = useState(
    localStorage.getItem("amh.nav-collapsed") === "true"
  );
  const [density, setDensityState] = useState<Density>(
    (localStorage.getItem("amh.density") as Density) || "standard"
  );
  const value = useMemo<Preferences>(
    () => ({
      theme,
      resolvedTheme:
        theme === "system" ? (systemDark ? "dark" : "light") : theme,
      setTheme: (next) => {
        localStorage.setItem("amh.theme", next);
        setThemeState(next);
      },
      navigationCollapsed,
      setNavigationCollapsed: (next) => {
        localStorage.setItem("amh.nav-collapsed", String(next));
        setNavigationCollapsed(next);
      },
      density,
      setDensity: (next) => {
        localStorage.setItem("amh.density", next);
        setDensityState(next);
      }
    }),
    [density, navigationCollapsed, systemDark, theme]
  );
  return (
    <PreferencesContext.Provider value={value}>
      {children}
    </PreferencesContext.Provider>
  );
}

export function usePreferences(): Preferences {
  const value = useContext(PreferencesContext);
  if (!value) throw new Error("PreferencesProvider nedostaje");
  return value;
}
