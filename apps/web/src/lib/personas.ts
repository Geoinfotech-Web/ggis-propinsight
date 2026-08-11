/** Target-user personas — mirrors API personas.py keys/labels. */

export type PersonaKey = "home_buyer" | "investor" | "tenant" | "developer";

export type PersonaDef = {
  key: PersonaKey;
  label: string;
  shortLabel: string;
  blurb: string;
  amenityOrder: readonly string[];
};

export const PERSONAS: PersonaDef[] = [
  {
    key: "home_buyer",
    label: "Home Buyer",
    shortLabel: "Buyer",
    blurb: "Family home — flood, schools & clinics, safety, access",
    amenityOrder: ["school", "hospital", "market", "bank"],
  },
  {
    key: "investor",
    label: "Investor",
    shortLabel: "Investor",
    blurb: "Yield & risk — market, tenure, security, flood",
    amenityOrder: ["bank", "market", "hospital", "school"],
  },
  {
    key: "tenant",
    label: "Tenant",
    shortLabel: "Tenant",
    blurb: "Day-to-day living — amenities, safety, access, habitability",
    amenityOrder: ["school", "hospital", "market", "bank"],
  },
  {
    key: "developer",
    label: "Developer",
    shortLabel: "Developer",
    blurb: "Land / estate — feasibility, tenure, flood, access",
    amenityOrder: ["market", "bank", "hospital", "school"],
  },
];

const STORAGE_KEY = "propinsight-persona";

export function loadPersona(): PersonaKey {
  if (typeof window === "undefined") return "home_buyer";
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved && PERSONAS.some((p) => p.key === saved)) return saved as PersonaKey;
  return "home_buyer";
}

export function savePersona(key: PersonaKey): void {
  localStorage.setItem(STORAGE_KEY, key);
}

export function getPersona(key: PersonaKey): PersonaDef {
  return PERSONAS.find((p) => p.key === key) ?? PERSONAS[0];
}
