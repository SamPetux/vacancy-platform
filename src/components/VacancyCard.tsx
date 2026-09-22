import Link from "next/link";

import type { Vacancy } from "@/lib/types";
import { formatSalary } from "@/lib/vacancy-utils";

const TYPE_STYLES: Record<Vacancy["type"], string> = {
  "Full-time": "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
  "Part-time": "bg-sky-100 text-sky-800 dark:bg-sky-500/15 dark:text-sky-300",
  Contract: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  Internship: "bg-violet-100 text-violet-800 dark:bg-violet-500/15 dark:text-violet-300",
};

export function VacancyCard({ vacancy }: { vacancy: Vacancy }) {
  return (
    <Link
      href={`/vacancies/${vacancy.id}`}
      className="group flex flex-col gap-3 rounded-xl border border-border bg-card p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-md"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold leading-tight group-hover:text-primary">
            {vacancy.title}
          </h3>
          <p className="text-sm text-muted">{vacancy.company}</p>
        </div>
        <span
          className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${TYPE_STYLES[vacancy.type]}`}
        >
          {vacancy.type}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
        <span className="inline-flex items-center gap-1">
          <span aria-hidden>📍</span>
          {vacancy.location}
        </span>
        {vacancy.remote && (
          <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
            <span aria-hidden>🌐</span>
            Remote
          </span>
        )}
        <span className="inline-flex items-center gap-1">
          <span aria-hidden>💰</span>
          {formatSalary(vacancy.salaryMin, vacancy.salaryMax)}
        </span>
      </div>

      {vacancy.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {vacancy.tags.map((tag) => (
            <span
              key={tag}
              className="rounded-md bg-background px-2 py-0.5 text-xs text-muted"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
    </Link>
  );
}
