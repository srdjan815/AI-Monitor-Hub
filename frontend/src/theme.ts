import { alpha, createTheme } from "@mui/material/styles";

export function createAppTheme(mode: "light" | "dark") {
  const navy = "#123047";
  const cyan = "#16a4a7";
  return createTheme({
    palette: {
      mode,
      primary: { main: mode === "light" ? navy : "#72c8d0" },
      secondary: { main: cyan },
      background: {
        default: mode === "light" ? "#f4f7f8" : "#0c1419",
        paper: mode === "light" ? "#ffffff" : "#121e25"
      },
      success: { main: "#2f8f68" },
      warning: { main: "#b77818" },
      error: { main: "#c84b4b" },
      info: { main: "#3979a8" }
    },
    shape: { borderRadius: 12 },
    typography: {
      fontFamily:
        '"Inter", "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
      h1: { fontSize: "1.75rem", fontWeight: 720, letterSpacing: "-0.03em" },
      h2: { fontSize: "1.25rem", fontWeight: 700 },
      h3: { fontSize: "1rem", fontWeight: 700 },
      button: { textTransform: "none", fontWeight: 650 }
    },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          body: { minWidth: 320 },
          "*:focus-visible": {
            outline: `3px solid ${alpha(cyan, 0.45)}`,
            outlineOffset: 2
          }
        }
      },
      MuiPaper: {
        styleOverrides: {
          root: {
            backgroundImage: "none",
            border: `1px solid ${alpha(mode === "light" ? navy : "#fff", 0.09)}`
          }
        }
      },
      MuiButton: { defaultProps: { disableElevation: true } },
      MuiTooltip: { defaultProps: { arrow: true, enterDelay: 450 } }
    }
  });
}
