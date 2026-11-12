export const TYPE_COLORS: Record<string, string> = {
  project: "#0f9488", team: "#4f46e5", system: "#d97706", plan: "#e11d48", entity: "#64748b",
};
export const colorFor = (type: string): string => TYPE_COLORS[type] ?? TYPE_COLORS.entity;
export const REL_LABEL = (rel: string): string => rel.toLowerCase().replace(/_/g, " ");
