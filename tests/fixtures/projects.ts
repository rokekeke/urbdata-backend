import type { components } from "../../app/lib/api/schema";

type Project = components["schemas"]["ProjectOut"];

export const projectFixtures: Project[] = [
  {
    id: "11111111-1111-4111-8111-111111111111",
    name: "Residencial Vandressen",
    municipality: "Florianópolis",
    state: "SC",
    typology: "Parcelamento do solo",
    approx_area_m2: 348_200,
    description: "Fixture contratual do frontend.",
    team: "Urbanismo",
    created_at: "2026-07-19T12:00:00Z",
  },
];
