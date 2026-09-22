"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { EMPLOYMENT_TYPES, type EmploymentType } from "@/lib/types";

const inputClass =
  "w-full rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20";

export default function PostVacancyPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  const [form, setForm] = useState({
    title: "",
    company: "",
    location: "",
    remote: false,
    type: "Full-time" as EmploymentType,
    salaryMin: "",
    salaryMax: "",
    description: "",
    tags: "",
  });

  function update<K extends keyof typeof form>(
    key: K,
    value: (typeof form)[K],
  ) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setErrors([]);

    const res = await fetch("/api/vacancies", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...form,
        salaryMin: form.salaryMin === "" ? null : Number(form.salaryMin),
        salaryMax: form.salaryMax === "" ? null : Number(form.salaryMax),
        tags: form.tags,
      }),
    });

    const data = await res.json();
    setSubmitting(false);

    if (!res.ok) {
      setErrors(data.errors ?? ["Something went wrong."]);
      return;
    }

    router.push(`/vacancies/${data.vacancy.id}`);
    router.refresh();
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-1 text-2xl font-bold">Post a vacancy</h1>
      <p className="mb-6 text-sm text-muted">
        Fill in the details below. Fields marked * are required.
      </p>

      {errors.length > 0 && (
        <div className="mb-4 rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-800 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-300">
          <ul className="list-inside list-disc">
            {errors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm font-medium">
            Title *
            <input
              className={inputClass}
              value={form.title}
              onChange={(e) => update("title", e.target.value)}
              placeholder="Senior Frontend Engineer"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Company *
            <input
              className={inputClass}
              value={form.company}
              onChange={(e) => update("company", e.target.value)}
              placeholder="Northwind Labs"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Location *
            <input
              className={inputClass}
              value={form.location}
              onChange={(e) => update("location", e.target.value)}
              placeholder="Berlin, Germany"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Employment type *
            <select
              className={inputClass}
              value={form.type}
              onChange={(e) => update("type", e.target.value as EmploymentType)}
            >
              {EMPLOYMENT_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Minimum salary
            <input
              className={inputClass}
              type="number"
              value={form.salaryMin}
              onChange={(e) => update("salaryMin", e.target.value)}
              placeholder="85000"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Maximum salary
            <input
              className={inputClass}
              type="number"
              value={form.salaryMax}
              onChange={(e) => update("salaryMax", e.target.value)}
              placeholder="110000"
            />
          </label>
        </div>

        <label className="flex items-center gap-2 text-sm font-medium">
          <input
            type="checkbox"
            checked={form.remote}
            onChange={(e) => update("remote", e.target.checked)}
            className="h-4 w-4 accent-[var(--primary)]"
          />
          This role can be done remotely
        </label>

        <label className="flex flex-col gap-1 text-sm font-medium">
          Tags (comma separated)
          <input
            className={inputClass}
            value={form.tags}
            onChange={(e) => update("tags", e.target.value)}
            placeholder="React, TypeScript, Remote"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm font-medium">
          Description *
          <textarea
            className={`${inputClass} min-h-32 resize-y`}
            value={form.description}
            onChange={(e) => update("description", e.target.value)}
            placeholder="Describe the role, responsibilities, and requirements…"
          />
        </label>

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-primary px-5 py-2.5 font-medium text-white transition hover:opacity-90 disabled:opacity-60"
          >
            {submitting ? "Publishing…" : "Publish vacancy"}
          </button>
        </div>
      </form>
    </div>
  );
}
