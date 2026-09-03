import { Divider, Stack, Typography } from "@mui/material";

function display(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

export function RecordDetails({
  record,
  exclude = []
}: {
  record: Record<string, unknown>;
  exclude?: string[];
}) {
  return (
    <Stack divider={<Divider flexItem />} gap={1.25}>
      {Object.entries(record)
        .filter(([key]) => !exclude.includes(key))
        .map(([key, value]) => (
          <Stack key={key} gap={0.4}>
            <Typography variant="caption" color="text.secondary">
              {key.replaceAll("_", " ").toUpperCase()}
            </Typography>
            <Typography
              component="pre"
              sx={{
                m: 0,
                whiteSpace: "pre-wrap",
                overflowWrap: "anywhere",
                fontFamily: typeof value === "object" ? "monospace" : "inherit",
                fontSize: "0.875rem"
              }}
            >
              {display(value)}
            </Typography>
          </Stack>
        ))}
    </Stack>
  );
}
