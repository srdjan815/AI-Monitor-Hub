import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CloseRounded,
  SearchRounded
} from "@mui/icons-material";
import {
  Box,
  CircularProgress,
  ClickAwayListener,
  IconButton,
  InputAdornment,
  List,
  ListItemButton,
  ListItemText,
  Paper,
  TextField,
  Tooltip,
  Typography
} from "@mui/material";
import { useNavigate } from "react-router-dom";
import { supplierApi } from "../api/supplierApi";
import { StatusChip } from "./StatusChip";

const resourceRoutes: Record<string, string> = {
  supplier: "/suppliers",
  source_connection: "/sources",
  acquisition: "/acquisitions",
  snapshot: "/snapshots",
  delta: "/deltas",
  incident: "/incidents"
};

export function GlobalSearch({ compact = false }: { compact?: boolean }) {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(query.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [query]);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);
  const search = useQuery({
    queryKey: ["global-search", debounced],
    queryFn: () => supplierApi.search(debounced, 15),
    enabled: debounced.length >= 2,
    staleTime: 15_000
  });
  const clear = () => {
    setQuery("");
    setDebounced("");
  };
  return (
    <ClickAwayListener onClickAway={() => setDebounced("")}>
      <Box position="relative" width={compact ? "100%" : { xs: 180, md: 380 }}>
        <TextField
          inputRef={inputRef}
          fullWidth
          size="small"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Pretraži dobavljače, run-ove, incidente…"
          aria-label="Globalna pretraga"
          InputProps={{
            startAdornment: (
              <InputAdornment position="start"><SearchRounded /></InputAdornment>
            ),
            endAdornment: (
              <InputAdornment position="end">
                {search.isFetching && <CircularProgress size={18} />}
                {query && (
                  <Tooltip title="Obriši pretragu">
                    <IconButton size="small" onClick={clear} aria-label="Obriši">
                      <CloseRounded fontSize="small" />
                    </IconButton>
                  </Tooltip>
                )}
              </InputAdornment>
            )
          }}
        />
        {debounced.length >= 2 && (
          <Paper
            elevation={8}
            sx={{
              position: "absolute",
              top: "calc(100% + 8px)",
              left: 0,
              right: 0,
              zIndex: 1500,
              maxHeight: 440,
              overflow: "auto"
            }}
          >
            {search.isError ? (
              <Typography color="error" p={2}>Pretraga trenutno nije dostupna.</Typography>
            ) : search.data?.items.length === 0 ? (
              <Typography color="text.secondary" p={2}>Nema rezultata.</Typography>
            ) : (
              <List dense>
                {search.data?.items.map((item) => (
                  <ListItemButton
                    key={`${item.resource_type}-${item.id}`}
                    onClick={() => {
                      navigate(resourceRoutes[item.resource_type] ?? "/dashboard", {
                        state: { openId: item.id }
                      });
                      clear();
                    }}
                  >
                    <ListItemText
                      primary={item.display_name}
                      secondary={`${item.resource_type} · ${item.code}`}
                    />
                    <StatusChip value={item.status} />
                  </ListItemButton>
                ))}
              </List>
            )}
          </Paper>
        )}
      </Box>
    </ClickAwayListener>
  );
}
