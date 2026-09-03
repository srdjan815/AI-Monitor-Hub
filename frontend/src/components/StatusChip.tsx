import {
  BlockRounded,
  CheckCircleRounded,
  ErrorRounded,
  HourglassTopRounded,
  InfoRounded,
  PauseCircleRounded,
  PlayCircleRounded,
  WarningRounded
} from "@mui/icons-material";
import { Chip, Tooltip } from "@mui/material";

const success = new Set(["ACTIVE", "READY", "SUCCEEDED", "VALID", "RESOLVED", "MANUALLY_APPROVED", "AUTO_RELEASED"]);
const error = new Set(["FAILED", "ERROR", "CRITICAL", "INVALID"]);
const warning = new Set([
  "PARTIALLY_SUCCEEDED",
  "OPEN",
  "HIGH",
  "P1",
  "P2",
  "RESTORING"
  ,"PENDING_REVIEW"
]);
const muted = new Set([
  "INACTIVE",
  "ARCHIVED",
  "DISMISSED",
  "SUPPRESSED",
  "CANCELLED"
  ,"REJECTED", "SUPERSEDED"
]);
const running = new Set(["RUNNING", "BUILDING", "IN_PROGRESS"]);

export function StatusChip({
  value,
  label,
  size = "small"
}: {
  value?: string | null;
  label?: string;
  size?: "small" | "medium";
}) {
  const status = value || "NEPOZNATO";
  const color = success.has(status)
    ? "success"
    : error.has(status)
      ? "error"
      : warning.has(status)
        ? "warning"
        : running.has(status)
          ? "info"
          : muted.has(status)
            ? "default"
            : "info";
  const Icon = success.has(status)
    ? CheckCircleRounded
    : error.has(status)
      ? ErrorRounded
      : warning.has(status)
        ? WarningRounded
        : running.has(status)
          ? PlayCircleRounded
          : muted.has(status)
            ? PauseCircleRounded
            : status === "PENDING"
              ? HourglassTopRounded
              : status === "BLOCKED"
                ? BlockRounded
                : InfoRounded;
  return (
    <Tooltip title={`Status: ${status}`}>
      <Chip
        icon={<Icon />}
        label={label ?? status.replaceAll("_", " ")}
        color={color}
        variant={color === "default" ? "outlined" : "filled"}
        size={size}
        sx={{ fontWeight: 700 }}
      />
    </Tooltip>
  );
}
