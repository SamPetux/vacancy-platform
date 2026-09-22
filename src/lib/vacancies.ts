import { promises as fs } from "node:fs";
import path from "node:path";
import { randomUUID } from "node:crypto";

import type { Vacancy, VacancyFilter, VacancyInput } from "@/lib/types";
import { filterVacancies, sortByNewest } from "@/lib/vacancy-utils";

const DATA_DIR = path.join(process.cwd(), "data");
const DATA_FILE = path.join(DATA_DIR, "vacancies.json");
const SEED_FILE = path.join(DATA_DIR, "vacancies.seed.json");

async function fileExists(filePath: string): Promise<boolean> {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

/**
 * Ensures the runtime data file exists, seeding it from the committed seed file
 * on first run. The runtime file is gitignored so local writes never dirty the
 * working tree.
 */
async function ensureDataFile(): Promise<void> {
  await fs.mkdir(DATA_DIR, { recursive: true });
  if (!(await fileExists(DATA_FILE))) {
    const seed = await fs.readFile(SEED_FILE, "utf-8");
    await fs.writeFile(DATA_FILE, seed, "utf-8");
  }
}

async function readAll(): Promise<Vacancy[]> {
  await ensureDataFile();
  const raw = await fs.readFile(DATA_FILE, "utf-8");
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as Vacancy[]) : [];
  } catch {
    return [];
  }
}

async function writeAll(vacancies: Vacancy[]): Promise<void> {
  await ensureDataFile();
  await fs.writeFile(DATA_FILE, JSON.stringify(vacancies, null, 2), "utf-8");
}

export async function listVacancies(
  filter: VacancyFilter = {},
): Promise<Vacancy[]> {
  const all = await readAll();
  return sortByNewest(filterVacancies(all, filter));
}

export async function getVacancy(id: string): Promise<Vacancy | null> {
  const all = await readAll();
  return all.find((vacancy) => vacancy.id === id) ?? null;
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);
}

export async function createVacancy(input: VacancyInput): Promise<Vacancy> {
  const all = await readAll();

  const base = slugify(`${input.title}-${input.company}`) || "vacancy";
  let id = base;
  if (all.some((vacancy) => vacancy.id === id)) {
    id = `${base}-${randomUUID().slice(0, 8)}`;
  }

  const vacancy: Vacancy = {
    id,
    ...input,
    postedAt: new Date().toISOString(),
  };

  await writeAll([vacancy, ...all]);
  return vacancy;
}
