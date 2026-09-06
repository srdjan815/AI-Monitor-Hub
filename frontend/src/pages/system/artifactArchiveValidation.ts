export function archivePathError(value: string): string | null {
  const normalized = value.trim();
  if (!normalized) return "Unesite relativnu putanju, na primer: cenovnici";
  if (/^[A-Za-z]:[\\/]/.test(normalized) || normalized.startsWith("/") || normalized.startsWith("\\")) {
    return "Unesite samo relativnu putanju unutar montirane arhive, na primer: cenovnici. Windows putanja C:\\... podešava se na serveru, ne u ovom polju.";
  }
  if (normalized.split(/[\\/]/).includes("..")) return "Putanja ne sme da sadrži '..'.";
  if (normalized.includes("\\")) return "Koristite znak '/' za podfoldere, na primer: cenovnici/2026.";
  return null;
}

export function operationErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "object" && error !== null && "message" in error && typeof error.message === "string") return error.message;
  return "Operacija nije uspela.";
}
