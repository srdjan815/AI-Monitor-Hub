import {
  useMemo,
  useState,
  type ReactNode
} from "react";
import {
  CheckBoxOutlineBlankRounded,
  CheckBoxRounded,
  DensityLargeRounded,
  DensityMediumRounded,
  DensitySmallRounded,
  DownloadRounded,
  MoreVertRounded,
  RefreshRounded,
  ViewColumnRounded
} from "@mui/icons-material";
import {
  Box,
  Checkbox,
  FormControlLabel,
  IconButton,
  Menu,
  MenuItem,
  Pagination,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography
} from "@mui/material";
import { usePreferences } from "../state/PreferencesContext";
import { EmptyState, LoadingBlock } from "./AsyncState";

export interface Column<T> {
  key: string;
  label: string;
  tooltip: string;
  width?: number;
  sortable?: boolean;
  render: (row: T) => ReactNode;
  csv?: (row: T) => string | number | null | undefined;
}

function csvCell(value: unknown): string {
  const text = value == null ? "" : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

export function EntityTable<T extends { id: string }>({
  tableId,
  columns,
  rows,
  total,
  page,
  pageSize,
  loading,
  selected,
  onSelected,
  onPage,
  onSort,
  sortBy,
  sortOrder,
  onOpen,
  onRefresh,
  bulkActions
}: {
  tableId: string;
  columns: Column<T>[];
  rows: T[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  selected: string[];
  onSelected: (ids: string[]) => void;
  onPage: (page: number) => void;
  onSort?: (key: string) => void;
  sortBy?: string;
  sortOrder?: "asc" | "desc";
  onOpen: (row: T) => void;
  onRefresh: () => void;
  bulkActions?: ReactNode;
}) {
  const { density, setDensity } = usePreferences();
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);
  const [visible, setVisible] = useState<string[]>(() => {
    const saved = localStorage.getItem(`amh.table.${tableId}.columns`);
    return saved ? (JSON.parse(saved) as string[]) : columns.map((item) => item.key);
  });
  const shown = useMemo(
    () => columns.filter((column) => visible.includes(column.key)),
    [columns, visible]
  );
  const allSelected = rows.length > 0 && rows.every((row) => selected.includes(row.id));
  const padding = density === "compact" ? "checkbox" : "normal";

  const toggleColumn = (key: string) => {
    const next = visible.includes(key)
      ? visible.filter((item) => item !== key)
      : [...visible, key];
    if (next.length) {
      setVisible(next);
      localStorage.setItem(`amh.table.${tableId}.columns`, JSON.stringify(next));
    }
  };

  const exportCsv = () => {
    const header = shown.map((column) => csvCell(column.label)).join(",");
    const body = rows.map((row) =>
      shown
        .map((column) => csvCell(column.csv?.(row) ?? ""))
        .join(",")
    );
    const blob = new Blob([[header, ...body].join("\n")], {
      type: "text/csv;charset=utf-8"
    });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${tableId}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  };

  return (
    <Paper sx={{ overflow: "hidden" }}>
      <Stack
        direction={{ xs: "column", sm: "row" }}
        justifyContent="space-between"
        alignItems={{ xs: "stretch", sm: "center" }}
        px={1.5}
        py={1}
        gap={1}
      >
        <Box>
          {selected.length ? (
            <Stack direction="row" gap={1} alignItems="center">
              <Typography fontWeight={700}>{selected.length} izabrano</Typography>
              {bulkActions}
            </Stack>
          ) : (
            <Typography color="text.secondary" variant="body2">
              {total.toLocaleString("sr-RS")} zapisa
            </Typography>
          )}
        </Box>
        <Stack direction="row" justifyContent="flex-end">
          <Tooltip title="Osveži podatke">
            <IconButton onClick={onRefresh} aria-label="Osveži podatke">
              <RefreshRounded />
            </IconButton>
          </Tooltip>
          <Tooltip title="Izvezi trenutno učitanu stranicu u CSV">
            <span>
              <IconButton
                onClick={exportCsv}
                disabled={!rows.length}
                aria-label="Izvezi CSV"
              >
                <DownloadRounded />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Kolone, gustina i sačuvani raspored">
            <IconButton
              onClick={(event) => setMenuAnchor(event.currentTarget)}
              aria-label="Podešavanja tabele"
            >
              <MoreVertRounded />
            </IconButton>
          </Tooltip>
          <Menu
            anchorEl={menuAnchor}
            open={Boolean(menuAnchor)}
            onClose={() => setMenuAnchor(null)}
          >
            <MenuItem disabled>
              <ViewColumnRounded fontSize="small" sx={{ mr: 1 }} />
              Vidljive kolone
            </MenuItem>
            {columns.map((column) => (
              <MenuItem key={column.key} onClick={() => toggleColumn(column.key)}>
                <FormControlLabel
                  control={<Checkbox checked={visible.includes(column.key)} />}
                  label={column.label}
                />
              </MenuItem>
            ))}
            <MenuItem
              onClick={() => setDensity("compact")}
              selected={density === "compact"}
            >
              <DensitySmallRounded sx={{ mr: 1 }} /> Kompaktno
            </MenuItem>
            <MenuItem
              onClick={() => setDensity("standard")}
              selected={density === "standard"}
            >
              <DensityMediumRounded sx={{ mr: 1 }} /> Standardno
            </MenuItem>
            <MenuItem
              onClick={() => setDensity("comfortable")}
              selected={density === "comfortable"}
            >
              <DensityLargeRounded sx={{ mr: 1 }} /> Komforno
            </MenuItem>
          </Menu>
        </Stack>
      </Stack>
      {loading ? (
        <Box p={2}><LoadingBlock /></Box>
      ) : rows.length === 0 ? (
        <EmptyState />
      ) : (
        <TableContainer sx={{ maxHeight: "calc(100vh - 315px)", minHeight: 360 }}>
          <Table stickyHeader size={density === "comfortable" ? "medium" : "small"}>
            <TableHead>
              <TableRow>
                <TableCell padding="checkbox">
                  <Tooltip title="Izaberi sve zapise na stranici">
                    <Checkbox
                      icon={<CheckBoxOutlineBlankRounded />}
                      checkedIcon={<CheckBoxRounded />}
                      checked={allSelected}
                      indeterminate={selected.length > 0 && !allSelected}
                      onChange={() =>
                        onSelected(allSelected ? [] : rows.map((row) => row.id))
                      }
                      inputProps={{ "aria-label": "Izaberi sve" }}
                    />
                  </Tooltip>
                </TableCell>
                {shown.map((column) => (
                  <TableCell
                    key={column.key}
                    padding={padding}
                    sx={{
                      minWidth: column.width ?? 140,
                      resize: "horizontal",
                      overflow: "auto",
                      whiteSpace: "nowrap",
                      cursor: column.sortable ? "pointer" : "default"
                    }}
                    onClick={() => column.sortable && onSort?.(column.key)}
                  >
                    <Tooltip title={column.tooltip}>
                      <Stack direction="row" gap={0.5} alignItems="center">
                        <span>{column.label}</span>
                        {sortBy === column.key && (
                          <Typography component="span" aria-label={sortOrder}>
                            {sortOrder === "asc" ? "↑" : "↓"}
                          </Typography>
                        )}
                      </Stack>
                    </Tooltip>
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((row) => (
                <TableRow
                  hover
                  key={row.id}
                  selected={selected.includes(row.id)}
                  onDoubleClick={() => onOpen(row)}
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") onOpen(row);
                  }}
                  sx={{ cursor: "pointer" }}
                >
                  <TableCell padding="checkbox">
                    <Checkbox
                      checked={selected.includes(row.id)}
                      onChange={() =>
                        onSelected(
                          selected.includes(row.id)
                            ? selected.filter((id) => id !== row.id)
                            : [...selected, row.id]
                        )
                      }
                      inputProps={{ "aria-label": `Izaberi ${row.id}` }}
                    />
                  </TableCell>
                  {shown.map((column) => (
                    <TableCell key={column.key} padding={padding}>
                      {column.render(row)}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
      <Stack direction="row" justifyContent="flex-end" p={1.5}>
        <Pagination
          count={Math.max(1, Math.ceil(total / pageSize))}
          page={page + 1}
          onChange={(_, value) => onPage(value - 1)}
          color="primary"
          showFirstButton
          showLastButton
          aria-label="Stranice tabele"
        />
      </Stack>
    </Paper>
  );
}
