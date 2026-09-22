import { NextResponse, type NextRequest } from "next/server";

import { getVacancy } from "@/lib/vacancies";

export async function GET(
  _request: NextRequest,
  ctx: RouteContext<"/api/vacancies/[id]">,
) {
  const { id } = await ctx.params;
  const vacancy = await getVacancy(id);

  if (!vacancy) {
    return NextResponse.json(
      { error: "Vacancy not found." },
      { status: 404 },
    );
  }

  return NextResponse.json({ vacancy });
}
