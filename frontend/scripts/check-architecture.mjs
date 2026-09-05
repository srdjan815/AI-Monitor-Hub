import { readFileSync, readdirSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = fileURLToPath(new URL("..", import.meta.url));
const limits = new Map([
  ["src/pages/SourcesPage.tsx", 750],
  ["src/pages/ScopedResourcePage.tsx", 750],
  ["src/pages/MappingProfilesPage.tsx", 500],
  ["src/pages/AutomationPage.tsx", 400],
]);
const featureDirectories = ["src/pages/sources", "src/pages/scopedResource", "src/pages/mapping", "src/pages/automation"];

for (const directory of featureDirectories) {
  for (const entry of readdirSync(join(frontendRoot, directory), { withFileTypes: true })) {
    if (entry.isFile() && /\.(?:ts|tsx)$/.test(entry.name) && !entry.name.endsWith(".test.ts")) {
      limits.set(join(directory, entry.name).replaceAll("\\", "/"), 500);
    }
  }
}

const violations = [];
for (const [file, limit] of limits) {
  const source = readFileSync(join(frontendRoot, file), "utf8");
  const lines = source.split(/\r?\n/).length;
  if (lines > limit) violations.push(`${file}: ${lines} linija (limit ${limit})`);
}

if (violations.length) {
  console.error("Frontend arhitektonski limiti su prekoračeni:\n" + violations.join("\n"));
  process.exitCode = 1;
} else {
  console.log(`Frontend arhitektonski limiti prolaze za ${limits.size} fajlova.`);
}
