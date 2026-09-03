import { useMemo, useState } from "react";
import {
  AccountTreeRounded,
  AdminPanelSettingsRounded,
  ArchiveRounded,
  BusinessRounded,
  ChevronLeftRounded,
  ChevronRightRounded,
  DashboardRounded,
  DarkModeRounded,
  DifferenceRounded,
  ErrorOutlineRounded,
  HubRounded,
  LightModeRounded,
  LogoutRounded,
  MenuRounded,
  NotificationsNoneRounded,
  ScheduleRounded,
  SchemaRounded,
  SettingsBrightnessRounded,
  StorageRounded,
  SyncRounded
} from "@mui/icons-material";
import {
  AppBar,
  Avatar,
  Box,
  Breadcrumbs,
  CssBaseline,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Stack,
  ThemeProvider,
  Toolbar,
  Tooltip,
  Typography,
  useMediaQuery
} from "@mui/material";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../state/AuthContext";
import { usePreferences } from "../state/PreferencesContext";
import { createAppTheme } from "../theme";
import { GlobalSearch } from "./GlobalSearch";
import { canAccess, PAGE_ACCESS } from "../accessControl";

const items = [
  { path: "/dashboard", label: "Dashboard", icon: DashboardRounded },
  { path: "/suppliers", label: "Dobavljači", icon: BusinessRounded },
  { path: "/sources", label: "Izvori", icon: HubRounded },
  { path: "/automation", label: "Automatski pokretač", icon: ScheduleRounded },
  { path: "/schemas", label: "Analiza cenovnika", icon: SchemaRounded },
  { path: "/mappings", label: "Mapiranje polja", icon: AccountTreeRounded },
  { path: "/acquisitions", label: "Import cenovnika", icon: SyncRounded },
  { path: "/snapshots", label: "Snapshots", icon: StorageRounded },
  { path: "/deltas", label: "Delta Runs", icon: DifferenceRounded },
  { path: "/incidents", label: "Incident centar", icon: ErrorOutlineRounded },
  { path: "/archive", label: "Arhiva", icon: ArchiveRounded },
  { path: "/administration", label: "Administracija", icon: AdminPanelSettingsRounded }
];

export function AppShell() {
  const auth = useAuth();
  const { logout } = auth;
  const preferences = usePreferences();
  const desktop = useMediaQuery("(min-width:900px)");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [userAnchor, setUserAnchor] = useState<HTMLElement | null>(null);
  const drawerWidth = preferences.navigationCollapsed ? 76 : 252;
  const theme = useMemo(
    () => createAppTheme(preferences.resolvedTheme),
    [preferences.resolvedTheme]
  );
  const location = useLocation();
  const visibleItems = items.filter((item) => {
    const access = PAGE_ACCESS.find((page) => page.path === item.path);
    return Boolean(access && canAccess(auth.permissions, access.permission));
  });
  const current = visibleItems.find((item) => location.pathname.startsWith(item.path));
  const navigation = (
    <Stack height="100%">
      <Stack direction="row" alignItems="center" gap={1.3} p={2}>
        <Avatar sx={{ bgcolor: "secondary.main", width: 36, height: 36 }}>AI</Avatar>
        {!preferences.navigationCollapsed && (
          <Box>
            <Typography fontWeight={800} lineHeight={1.1}>AI Monitor Hub</Typography>
            <Typography variant="caption" color="text.secondary">
              Supplier Platform
            </Typography>
          </Box>
        )}
      </Stack>
      <Divider />
      <List sx={{ p: 1, flex: 1 }}>
        {visibleItems.map(({ path, label, icon: Icon }) => (
          <Tooltip
            title={preferences.navigationCollapsed ? label : ""}
            key={path}
          >
            <ListItemButton
              component={NavLink}
              to={path}
              onClick={() => setMobileOpen(false)}
              sx={{
                borderRadius: 2,
                mb: 0.5,
                "&.active": {
                  bgcolor: "action.selected",
                  color: "primary.main",
                  "& .MuiListItemIcon-root": { color: "primary.main" }
                }
              }}
            >
              <ListItemIcon sx={{ minWidth: 42 }}><Icon /></ListItemIcon>
              {!preferences.navigationCollapsed && <ListItemText primary={label} />}
            </ListItemButton>
          </Tooltip>
        ))}
      </List>
      {desktop && (
        <>
          <Divider />
          <Tooltip title={preferences.navigationCollapsed ? "Raširi navigaciju" : "Skupi navigaciju"}>
            <IconButton
              onClick={() =>
                preferences.setNavigationCollapsed(!preferences.navigationCollapsed)
              }
              sx={{ m: 1, alignSelf: preferences.navigationCollapsed ? "center" : "flex-end" }}
              aria-label="Promeni širinu navigacije"
            >
              {preferences.navigationCollapsed ? <ChevronRightRounded /> : <ChevronLeftRounded />}
            </IconButton>
          </Tooltip>
        </>
      )}
    </Stack>
  );
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box display="flex" minHeight="100vh">
        <AppBar
          position="fixed"
          color="inherit"
          elevation={0}
          sx={{
            ml: { md: `${drawerWidth}px` },
            width: { md: `calc(100% - ${drawerWidth}px)` },
            borderBottom: 1,
            borderColor: "divider"
          }}
        >
          <Toolbar sx={{ gap: 1.5 }}>
            {!desktop && (
              <IconButton onClick={() => setMobileOpen(true)} aria-label="Otvori navigaciju">
                <MenuRounded />
              </IconButton>
            )}
            {auth.can("supplier_platform.search") && <GlobalSearch />}
            <Box flex={1} />
            {auth.can("incidents.read") && (
              <Tooltip title="Obaveštenja su vezana za Incident centar">
                <IconButton component={Link} to="/incidents" aria-label="Obaveštenja">
                  <NotificationsNoneRounded />
                </IconButton>
              </Tooltip>
            )}
            <Tooltip title="Korisnički meni">
              <IconButton
                onClick={(event) => setUserAnchor(event.currentTarget)}
                aria-label="Korisnički meni"
              >
                <Avatar sx={{ width: 32, height: 32 }}>A</Avatar>
              </IconButton>
            </Tooltip>
            <Menu
              anchorEl={userAnchor}
              open={Boolean(userAnchor)}
              onClose={() => setUserAnchor(null)}
            >
              <MenuItem onClick={() => preferences.setTheme("light")}>
                <LightModeRounded sx={{ mr: 1 }} /> Svetla tema
              </MenuItem>
              <MenuItem onClick={() => preferences.setTheme("dark")}>
                <DarkModeRounded sx={{ mr: 1 }} /> Tamna tema
              </MenuItem>
              <MenuItem onClick={() => preferences.setTheme("system")}>
                <SettingsBrightnessRounded sx={{ mr: 1 }} /> Sistemska tema
              </MenuItem>
              <Divider />
              <MenuItem onClick={logout}>
                <LogoutRounded sx={{ mr: 1 }} /> Odjavi se
              </MenuItem>
            </Menu>
          </Toolbar>
        </AppBar>
        <Drawer
          variant={desktop ? "permanent" : "temporary"}
          open={desktop || mobileOpen}
          onClose={() => setMobileOpen(false)}
          sx={{
            width: { md: drawerWidth },
            "& .MuiDrawer-paper": {
              width: drawerWidth,
              boxSizing: "border-box",
              transition: "width .2s ease"
            }
          }}
        >
          {navigation}
        </Drawer>
        <Box
          component="main"
          flex={1}
          minWidth={0}
          ml={{ md: `${drawerWidth}px` }}
          pt="64px"
        >
          <Box px={{ xs: 2, md: 3.5 }} py={2}>
            <Breadcrumbs aria-label="Navigaciona putanja" sx={{ mb: 2 }}>
              {visibleItems[0] ? (
                <Link to={visibleItems[0].path} style={{ color: "inherit" }}>Supplier Platform</Link>
              ) : (
                <Typography color="text.secondary">Supplier Platform</Typography>
              )}
              <Typography color="text.primary">{current?.label ?? "Radni prostor"}</Typography>
            </Breadcrumbs>
            <Outlet />
          </Box>
        </Box>
      </Box>
    </ThemeProvider>
  );
}
