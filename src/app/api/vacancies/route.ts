import { NextResponse, type NextRequest } from "next/server";

import { createVacancy, listVacancies } from "@/lib/vacancies";
import { validateVacancyInput } from "@/lib/vacancy-utils";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const vacancies = await listVacancies({
    search: searchParams.get("search") ?? undefined,
    type: searchParams.get("type") ?? undefined,
    remoteOnly: searchParams.get("remote") === "true",
  });

  return NextResponse.json({ vacancies });
}

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { errors: ["Request body must be valid JSON."] },
      { status: 400 },
    );
  }

  const { input, errors } = validateVacancyInput(body);
  if (!input) {
    return NextResponse.json({ errors }, { status: 400 });
  }

  const vacancy = await createVacancy(input);
  return NextResponse.json({ vacancy }, { status: 201 });
}
