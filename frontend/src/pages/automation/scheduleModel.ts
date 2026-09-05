export const initialScheduleForm = {
  status: "ENABLED",
  schedule_type: "DAILY",
  times: "06:00",
  weekdays: [1, 2, 3, 4, 5] as number[],
  interval_hours: 6,
  automation_depth: "FULL_PIPELINE",
  timeout_seconds: 300,
  max_attempts: 3,
};

export type ScheduleForm = typeof initialScheduleForm;
export const ALL_SUPPLIERS = "__all_suppliers__";
export const dayNames = ["Ponedeljak", "Utorak", "Sreda", "Četvrtak", "Petak", "Subota", "Nedelja"];
