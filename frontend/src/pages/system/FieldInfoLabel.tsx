import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import { Stack, Tooltip, Typography } from "@mui/material";

interface FieldInfoLabelProps {
  label: string;
  help: string;
}

export function FieldInfoLabel({ label, help }: FieldInfoLabelProps) {
  return <Stack direction="row" alignItems="center" gap={0.5}>
    <Typography variant="caption" color="text.secondary">{label}</Typography>
    <Tooltip title={help} arrow>
      <InfoOutlinedIcon color="info" fontSize="small" tabIndex={0} aria-label={help} />
    </Tooltip>
  </Stack>;
}
