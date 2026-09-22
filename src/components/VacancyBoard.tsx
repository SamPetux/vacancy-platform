"use client";

import { useEffect, useState } from "react";

import { EMPLOYMENT_TYPES } from "@/lib/types";
import type { Vacancy } from "@/lib/types";
import { VacancyCard } from "@/components/VacancyCard";

export function VacancyBoard({ initial }: { initial: Vacancy[] }) {
  const [vacancies, setVacancies] = useState<Vacancy[]>(initial);
  const [search, setSearch] = useState("");
  const [type, setType] = useState("");
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setLoading(true);
      const params = new URLSearchParams();
      if (search.trim()) params.set("search", search.trim());
      if (type) params.set("type", type);
      if (remoteOnly) params.set("remote", "true");

      try {
        const res = await fetch(`/api/vacancies?${params.toString()}`, {
          signal: controller.signal,
        });
        const data = await res.json();
        setVacancies(data.vacancies ?? []);
      } catch (error) {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          console.error(error);
        }
      } finally {
        setLoading(false);
      }
    }, 200);

    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [search, type, remoteOnly]);

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search title, company, skills…"
          aria-label="Search vacancies"
          className="w-full rounded-lg border border-border bg-card px-4 py-2.5 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
        />
        <select
          value={type}
          onChange={(event) => setType(event.target.value)}
          aria-label="Filter by employment type"
          className="rounded-lg border border-border bg-card px-3 py-2.5 text-sm outline-none focus:border-primary"
        >
          <option value="">All types</option>
          {EMPLOYMENT_TYPES.map((employmentType) => (
            <option key={employmentType} value={employmentType}>
              {employmentType}
            </option>
          ))}
        </select>
        <label className="flex shrink-0 items-center gap-2 rounded-lg border border-border bg-card px-3 py-2.5 text-sm">
          <input
            type="checkbox"
            checked={remoteOnly}
            onChange={(event) => setRemoteOnly(event.target.checked)}
            className="h-4 w-4 accent-[var(--primary)]"
          />
          Remote only
        </label>
      </div>

      <p className="text-sm text-muted" aria-live="polite">
        {loading
          ? "Loading…"
          : `${vacancies.length} ${vacancies.length === 1 ? "vacancy" : "vacancies"} found`}
      </p>

      {vacancies.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border bg-card p-10 text-center text-muted">
          No vacancies match your filters.
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {vacancies.map((vacancy) => (
            <VacancyCard key={vacancy.id} vacancy={vacancy} />
          ))}
        </div>
      )}
    </section>
  );
}
