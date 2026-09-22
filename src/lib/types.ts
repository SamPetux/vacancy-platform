export const EMPLOYMENT_TYPES = [
  "Full-time",
  "Part-time",
  "Contract",
  "Internship",
] as const;

export type EmploymentType = (typeof EMPLOYMENT_TYPES)[number];

export interface Vacancy {
  id: string;
  title: string;
  company: string;
  location: string;
  remote: boolean;
  type: EmploymentType;
  salaryMin: number | null;
  salaryMax: number | null;
  description: string;
  tags: string[];
  postedAt: string;
}

export interface VacancyInput {
  title: string;
  company: string;
  location: string;
  remote: boolean;
  type: EmploymentType;
  salaryMin: number | null;
  salaryMax: number | null;
  description: string;
  tags: string[];
}

export interface VacancyFilter {
  search?: string;
  type?: string;
  remoteOnly?: boolean;
}
