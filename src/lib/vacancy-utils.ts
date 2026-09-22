import { EMPLOYMENT_TYPES, type EmploymentType } from "@/lib/types";
import type { Vacancy, VacancyFilter, VacancyInput } from "@/lib/types";

export function isEmploymentType(value: unknown): value is EmploymentType {
  return (
    typeof value === "string" &&
    (EMPLOYMENT_TYPES as readonly string[]).includes(value)
  );
}

/**
 * Applies free-text search, employment-type, and remote filters to a list of
 * vacancies. Kept pure (no I/O) so it is trivial to unit test.
 */
export function filterVacancies(
  vacancies: Vacancy[],
  filter: VacancyFilter,
): Vacancy[] {
  const search = filter.search?.trim().toLowerCase();

  return vacancies.filter((vacancy) => {
    if (filter.type && vacancy.type !== filter.type) {
      return false;
    }

    if (filter.remoteOnly && !vacancy.remote) {
      return false;
    }

    if (search) {
      const haystack = [
        vacancy.title,
        vacancy.company,
        vacancy.location,
        vacancy.description,
        vacancy.tags.join(" "),
      ]
        .join(" ")
        .toLowerCase();

      if (!haystack.includes(search)) {
        return false;
      }
    }

    return true;
  });
}

export function sortByNewest(vacancies: Vacancy[]): Vacancy[] {
  return [...vacancies].sort(
    (a, b) => new Date(b.postedAt).getTime() - new Date(a.postedAt).getTime(),
  );
}

export interface ValidationResult {
  input?: VacancyInput;
  errors: string[];
}

function toOptionalNumber(value: unknown): number | null | undefined {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

/**
 * Validates and normalizes untrusted input (e.g. an API request body) into a
 * `VacancyInput`. Returns collected human-readable errors when invalid.
 */
export function validateVacancyInput(raw: unknown): ValidationResult {
  const errors: string[] = [];

  if (typeof raw !== "object" || raw === null) {
    return { errors: ["Request body must be a JSON object."] };
  }

  const body = raw as Record<string, unknown>;

  const title = typeof body.title === "string" ? body.title.trim() : "";
  const company = typeof body.company === "string" ? body.company.trim() : "";
  const location = typeof body.location === "string" ? body.location.trim() : "";
  const description =
    typeof body.description === "string" ? body.description.trim() : "";

  if (!title) errors.push("Title is required.");
  if (!company) errors.push("Company is required.");
  if (!location) errors.push("Location is required.");
  if (description.length < 10) {
    errors.push("Description must be at least 10 characters.");
  }

  if (!isEmploymentType(body.type)) {
    errors.push(
      `Type must be one of: ${EMPLOYMENT_TYPES.join(", ")}.`,
    );
  }

  const salaryMin = toOptionalNumber(body.salaryMin);
  const salaryMax = toOptionalNumber(body.salaryMax);

  if (salaryMin === undefined) errors.push("Minimum salary must be a number.");
  if (salaryMax === undefined) errors.push("Maximum salary must be a number.");

  if (
    typeof salaryMin === "number" &&
    typeof salaryMax === "number" &&
    salaryMin > salaryMax
  ) {
    errors.push("Minimum salary cannot be greater than maximum salary.");
  }

  let tags: string[] = [];
  if (Array.isArray(body.tags)) {
    tags = body.tags
      .filter((tag): tag is string => typeof tag === "string")
      .map((tag) => tag.trim())
      .filter(Boolean);
  } else if (typeof body.tags === "string") {
    tags = body.tags
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean);
  }

  if (errors.length > 0 || !isEmploymentType(body.type)) {
    return { errors };
  }

  return {
    input: {
      title,
      company,
      location,
      remote: Boolean(body.remote),
      type: body.type,
      salaryMin: salaryMin ?? null,
      salaryMax: salaryMax ?? null,
      description,
      tags,
    },
    errors,
  };
}

export function formatSalary(
  min: number | null,
  max: number | null,
): string {
  const fmt = (value: number) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(value);

  if (min !== null && max !== null) return `${fmt(min)} – ${fmt(max)}`;
  if (min !== null) return `From ${fmt(min)}`;
  if (max !== null) return `Up to ${fmt(max)}`;
  return "Not disclosed";
}
