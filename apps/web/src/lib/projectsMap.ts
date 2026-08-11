import type { DevelopmentProject, Scorecard } from "../api";

export function mappedProjects(card: Scorecard | null): DevelopmentProject[] {
  const projects = card?.development_outlook?.projects?.nearby ?? [];
  return projects.filter(
    (project) => project.geometry?.type === "Point" && project.distance_m != null,
  );
}
