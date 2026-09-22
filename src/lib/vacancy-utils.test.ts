import { describe, expect, it } from "vitest";

import type { Vacancy } from "@/lib/types";
import {
  filterVacancies,
  formatSalary,
  sortByNewest,
  validateVacancyInput,
} from "@/lib/vacancy-utils";

function makeVacancy(overrides: Partial<Vacancy> = {}): Vacancy {
  return {
    id: "id",
    title: "Frontend Engineer",
    company: "Acme",
    location: "Berlin",
    remote: false,
    type: "Full-time",
    salaryMin: 50000,
    salaryMax: 70000,
    description: "A great role",
    tags: ["React"],
    postedAt: "2026-01-01T00:00:00.000Z",
    ...overrides,
  };
}

describe("filterVacancies", () => {
  const vacancies = [
    makeVacancy({ id: "1", title: "React Engineer", tags: ["React"] }),
    makeVacancy({
      id: "2",
      title: "Go Backend",
      type: "Contract",
      remote: true,
      tags: ["Go"],
    }),
    makeVacancy({ id: "3", company: "Vercel", tags: ["Design"] }),
  ];

  it("returns all vacancies when no filter is provided", () => {
    expect(filterVacancies(vacancies, {})).toHaveLength(3);
  });

  it("matches free-text search across fields (case-insensitive)", () => {
    expect(filterVacancies(vacancies, { search: "react" })).toHaveLength(1);
    expect(filterVacancies(vacancies, { search: "vercel" })[0].id).toBe("3");
  });

  it("filters by employment type", () => {
    const result = filterVacancies(vacancies, { type: "Contract" });
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("2");
  });

  it("filters remote-only roles", () => {
    const result = filterVacancies(vacancies, { remoteOnly: true });
    expect(result.map((v) => v.id)).toEqual(["2"]);
  });
});

describe("sortByNewest", () => {
  it("orders vacancies by postedAt descending", () => {
    const older = makeVacancy({ id: "old", postedAt: "2026-01-01T00:00:00Z" });
    const newer = makeVacancy({ id: "new", postedAt: "2026-06-01T00:00:00Z" });
    expect(sortByNewest([older, newer]).map((v) => v.id)).toEqual([
      "new",
      "old",
    ]);
  });
});

describe("formatSalary", () => {
  it("formats a range", () => {
    expect(formatSalary(50000, 70000)).toContain("50,000");
    expect(formatSalary(50000, 70000)).toContain("70,000");
  });

  it("handles open-ended and missing values", () => {
    expect(formatSalary(50000, null)).toMatch(/^From/);
    expect(formatSalary(null, 70000)).toMatch(/^Up to/);
    expect(formatSalary(null, null)).toBe("Not disclosed");
  });
});

describe("validateVacancyInput", () => {
  const valid = {
    title: "Engineer",
    company: "Acme",
    location: "Berlin",
    remote: true,
    type: "Full-time",
    salaryMin: 50000,
    salaryMax: 70000,
    description: "A sufficiently long description.",
    tags: "React, TypeScript",
  };

  it("accepts and normalizes valid input", () => {
    const { input, errors } = validateVacancyInput(valid);
    expect(errors).toHaveLength(0);
    expect(input).toBeDefined();
    expect(input?.tags).toEqual(["React", "TypeScript"]);
    expect(input?.remote).toBe(true);
  });

  it("rejects missing required fields", () => {
    const { input, errors } = validateVacancyInput({});
    expect(input).toBeUndefined();
    expect(errors.length).toBeGreaterThan(0);
  });

  it("rejects an invalid employment type", () => {
    const { input, errors } = validateVacancyInput({
      ...valid,
      type: "Freelance",
    });
    expect(input).toBeUndefined();
    expect(errors.some((e) => e.includes("Type must be one of"))).toBe(true);
  });

  it("rejects when min salary exceeds max salary", () => {
    const { input, errors } = validateVacancyInput({
      ...valid,
      salaryMin: 90000,
      salaryMax: 40000,
    });
    expect(input).toBeUndefined();
    expect(errors.some((e) => e.includes("greater than"))).toBe(true);
  });
});
