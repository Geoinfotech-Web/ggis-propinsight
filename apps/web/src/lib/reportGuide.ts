import { DOMAIN_ORDER, type DomainResult, type Scorecard } from "../api";
import type { PersonaKey } from "./personas";

export type GuideAction = {
  id: string;
  domain: string;
  title: string;
  detail: string;
  urgency: "important" | "recommended" | "routine";
};

export type GuideCoverage = {
  included: number;
  limited: number;
  unavailable: number;
};

const PROFESSIONAL_PERSONAS = new Set<PersonaKey>(["investor", "developer"]);
const CONSTRAINED_LAND_TERMS = [
  "reserve",
  "reserved",
  "protected",
  "conservation",
  "green belt",
  "forest",
  "water",
  "setback",
  "acquisition",
];

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function number(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function domainResult(card: Scorecard, domain: string): DomainResult | undefined {
  return card.domains[domain];
}

function domainRank(card: Scorecard, domain: string): number {
  const order = card.domain_priority?.length ? card.domain_priority : [...DOMAIN_ORDER];
  const index = order.indexOf(domain);
  return index === -1 ? order.length : index;
}

function actionPriority(action: GuideAction): number {
  return action.urgency === "important" ? 0 : action.urgency === "recommended" ? 1 : 2;
}

export function reportCoverage(card: Scorecard): GuideCoverage {
  const results = Object.values(card.domains);
  return {
    included: results.filter((result) => result.included_in_fit && result.score != null).length,
    limited: results.filter(
      (result) =>
        result.score != null && (result.status === "degraded" || result.status === "demo"),
    ).length,
    unavailable: results.filter(
      (result) => result.status === "pending" || result.score == null,
    ).length,
  };
}

export function buildNextSteps(card: Scorecard, persona: PersonaKey): GuideAction[] {
  const professional = PROFESSIONAL_PERSONAS.has(persona);
  const candidates: GuideAction[] = [];
  const landUseText = [
    card.location.land_use?.category,
    card.location.land_use?.label,
    card.location.land_use?.name,
    card.location.land_use?.source_class,
    card.location.land_use?.source_subtype,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  const constrainedLand = CONSTRAINED_LAND_TERMS.some((term) => landUseText.includes(term));

  if (constrainedLand) {
    candidates.push({
      id: "planning-constraint",
      domain: "tenure",
      urgency: "important",
      title: "Confirm the planning restriction before committing",
      detail:
        "The mapped context suggests reserved, protected, setback, or otherwise constrained land. Obtain written confirmation from AGIS/FCTA and verify the title before paying or designing.",
    });
  } else if (persona !== "tenant") {
    candidates.push({
      id: "planning-title",
      domain: "tenure",
      urgency: card.location.planning_status === "official" ? "routine" : "recommended",
      title: "Verify title and permitted land use",
      detail:
        card.location.planning_status === "official"
          ? "Confirm the current title, allocation conditions, setbacks, and development controls against the official planning record."
          : "This report does not contain a confirmed official plan for the point. Verify title and permitted use directly with AGIS/FCTA.",
    });
  }

  const flood = domainResult(card, "flood");
  const floodHazard = flood?.score;
  if (floodHazard == null || flood?.status === "degraded" || flood?.status === "demo") {
    candidates.push({
      id: "flood-unavailable",
      domain: "flood",
      urgency: "recommended",
      title: "Confirm flood history locally",
      detail:
        "Reliable flood evidence is limited for this point. Ask about past events and inspect drainage conditions before relying on the location.",
    });
  } else if (floodHazard >= 60) {
    candidates.push({
      id: "flood-high",
      domain: "flood",
      urgency: "important",
      title: "Commission a site-specific flood and drainage assessment",
      detail:
        "The location has high flood hazard. Check finished-floor levels, runoff routes, historical events, and mitigation cost before proceeding.",
    });
  } else if (floodHazard >= 40) {
    candidates.push({
      id: "flood-moderate",
      domain: "flood",
      urgency: "recommended",
      title: "Inspect drainage and past flood conditions",
      detail:
        "The flood signal is moderate. Visit after rainfall where possible and confirm drains, low points, access routes, and local flood history.",
    });
  }

  const feasibility = domainResult(card, "feasibility");
  const terrain = record(feasibility?.evidence.terrain);
  const drainage = record(feasibility?.evidence.drainage);
  const modelledDrainage = record(drainage.modelled);
  const servicing = record(feasibility?.evidence.servicing);
  const water = record(servicing.water);
  const power = record(servicing.power);
  const road = record(servicing.nearest_road);
  if (professional) {
    const buildableShare = number(terrain.buildable_share_pct);
    const slopeP90 = number(terrain.slope_p90_deg);
    if (feasibility?.score == null || (buildableShare != null && buildableShare < 70) || (slopeP90 != null && slopeP90 > 10)) {
      candidates.push({
        id: "terrain-survey",
        domain: "feasibility",
        urgency: feasibility?.score == null ? "important" : "recommended",
        title: "Obtain topographic and geotechnical surveys",
        detail:
          "Confirm buildable area, cut-and-fill, retaining requirements, soil conditions, and foundation implications before preparing a development concept.",
      });
    }
    const drainageDistance = number(modelledDrainage.distance_m);
    if (drainageDistance != null && drainageDistance <= 500 && floodHazard != null && floodHazard < 60) {
      candidates.push({
        id: "modelled-drainage",
        domain: "feasibility",
        urgency: "recommended",
        title: "Survey the nearby modelled drainage path",
        detail:
          "A terrain-derived flow path is close to the site. Confirm its position and capacity through field survey before fixing plots, roads, or finished levels.",
      });
    }
    const waterDistance = number(water.distance_m);
    const powerDistance = number(power.distance_m);
    const roadDistance = number(road.distance_m);
    if (
      waterDistance == null ||
      powerDistance == null ||
      roadDistance == null ||
      waterDistance > 3_000 ||
      powerDistance > 3_000 ||
      roadDistance > 1_000
    ) {
      candidates.push({
        id: "servicing-check",
        domain: "feasibility",
        urgency: "recommended",
        title: "Confirm utility capacity and legal access",
        detail:
          "Mapped proximity does not confirm a connection. Obtain provider capacity information, connection costs, wayleaves, and evidence of lawful road access.",
      });
    }
  }

  const market = domainResult(card, "market");
  if (market?.score == null || market.score < 40 || market.status !== "ok") {
    candidates.push({
      id: "market-check",
      domain: "market",
      urgency: "recommended",
      title: professional ? "Validate demand and comparable values" : "Confirm the current total housing cost",
      detail: professional
        ? "Collect recent verified sale or rental comparables, vacancy evidence, achievable pricing, and development-cost assumptions before relying on projected returns."
        : persona === "tenant"
          ? "Confirm current rent, service charges, utility arrangements, deposit terms, and transport costs with the landlord or agent."
          : "Compare recent verified sale prices and include service charges, infrastructure contributions, title costs, and likely maintenance expenses.",
    });
  }

  if (professional && card.development_outlook?.projects.total_count) {
    candidates.push({
      id: "project-verification",
      domain: "market",
      urgency: "routine",
      title: "Verify nearby government-project status",
      detail:
        "Open the official sources and distinguish budgeted, procurement, awarded, and ongoing projects. Do not price in delivery that has not been independently confirmed.",
    });
  }

  if (!professional) {
    const security = domainResult(card, "security");
    if (security?.score == null || security.score < 50 || security.status !== "ok") {
      candidates.push({
        id: "security-visit",
        domain: "security",
        urgency: "recommended",
        title: "Check the immediate area at different times",
        detail:
          "Visit during the day and evening, speak with residents, and confirm lighting, access control, transport availability, and the nearest practical police response point.",
      });
    }
    const amenities = domainResult(card, "amenities");
    const access = domainResult(card, "accessibility");
    if ((amenities?.score ?? 0) < 50 || (access?.score ?? 0) < 50) {
      candidates.push({
        id: "daily-routine",
        domain: "amenities",
        urgency: "recommended",
        title: "Test your everyday journeys",
        detail:
          "Travel the routes you would actually use for work, school, healthcare, shopping, and public transport at normal peak times.",
      });
    }
    const livability = domainResult(card, "livability");
    if (livability?.score == null || livability.score < 40) {
      candidates.push({
        id: "environment-visit",
        domain: "livability",
        urgency: "recommended",
        title: "Inspect heat, shade, noise, and drainage in person",
        detail:
          "Check afternoon heat, tree shade, ventilation, generator or traffic noise, waste handling, and standing water around the property.",
      });
    }
  }

  if (!candidates.length) {
    candidates.push({
      id: "independent-checks",
      domain: "tenure",
      urgency: "routine",
      title: "Complete independent due diligence",
      detail:
        "Verify the property, documents, current conditions, and quoted costs with the relevant authority and qualified professionals before committing.",
    });
  }

  const unique = [...new Map(candidates.map((item) => [item.id, item])).values()];
  return unique
    .sort((left, right) => {
      const urgency = actionPriority(left) - actionPriority(right);
      if (urgency !== 0) return urgency;
      return domainRank(card, left.domain) - domainRank(card, right.domain);
    })
    .slice(0, 5);
}
