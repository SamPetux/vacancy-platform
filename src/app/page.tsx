import { VacancyBoard } from "@/components/VacancyBoard";
import { listVacancies } from "@/lib/vacancies";

export const dynamic = "force-dynamic";

export default async function Home() {
  const vacancies = await listVacancies();

  return (
    <div className="flex flex-col gap-8">
      <section className="rounded-2xl bg-gradient-to-br from-primary to-indigo-400 px-6 py-10 text-white shadow-sm">
        <h1 className="text-3xl font-bold sm:text-4xl">
          Find your next role
        </h1>
        <p className="mt-2 max-w-xl text-white/90">
          Browse open positions from great teams, or post your own vacancy in
          under a minute.
        </p>
      </section>

      <VacancyBoard initial={vacancies} />
    </div>
  );
}
