import type { ApiError } from "../types";

export function normalizeScheduleTimes(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim().replace(/[.;]+$/, ""))
    .filter(Boolean)
    .map((item) => {
      const match = /^(\d{1,2}):(\d{2})$/.exec(item);
      const hour = match ? Number(match[1]) : -1;
      const minute = match ? Number(match[2]) : -1;
      if (!match || hour > 23 || minute > 59) {
        throw {
          status: 422,
          code: "schedule_time_invalid",
          message: `Vreme „${item}“ nije ispravno. Koristite oblik 08:30, 14:00.`
        } satisfies ApiError;
      }
      return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
    });
}
