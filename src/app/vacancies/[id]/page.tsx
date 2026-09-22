import Link from "next/link";
import { notFound } from "next/navigation";

import { getVacancy } from "@/lib/vacancies";
import { formatSalary } from "@/lib/vacancy-utils";

export const dynamic = "force-dynamic";

export default async function VacancyDetailPage({
  params,
}: PageProps<"/vacancies/[id]">) {
  const { id } = await params;
  const vacancy = await getVacancy(id);

  if (!vacancy) {
    notFound();
  }

  return (
    <article className="flex flex-col gap-6">
      <Link href="/" className="text-sm text-muted hover:text-foreground">
        ← Back to all vacancies
      </Link>

      <header className="flex flex-col gap-2 rounded-2xl border border-border bg-card p-6">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
            {vacancy.type}
          </span>
          {vacancy.remote && (
            <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-medium text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300">
              Remote
            </span>
          )}
        </div>
        <h1 className="text-2xl font-bold">{vacancy.title}</h1>
        <p className="text-muted">
          {vacancy.company} · {vacancy.location}
        </p>
        <p className="mt-1 font-medium">
          {formatSalary(vacancy.salaryMin, vacancy.salaryMax)}
        </p>
        <p className="text-sm text-muted">
          Posted {new Date(vacancy.postedAt).toLocaleDateString()}
        </p>
      </header>

      <section className="rounded-2xl border border-border bg-card p-6">
        <h2 className="mb-2 font-semibold">About the role</h2>
        <p className="whitespace-pre-line leading-relaxed text-foreground/90">
          {vacancy.description}
        </p>
      </section>

      {vacancy.tags.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {vacancy.tags.map((tag) => (
            <span
              key={tag}
              className="rounded-md bg-card px-2.5 py-1 text-sm text-muted ring-1 ring-border"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
    </article>
  );
}
