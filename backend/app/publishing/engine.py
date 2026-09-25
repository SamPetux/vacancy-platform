"""Template Engine facade — Vacancy → PostDraft → rendered text."""

from __future__ import annotations

from typing import Any

from app.models.vacancy import Vacancy
from app.models.vacancy_score import VacancyScore
from app.parsing.sections import merge_sections
from app.publishing.availability import assess_availability
from app.publishing.blocks import build_blocks, build_meta, choose_mode
from app.publishing.editorial import build_editorial
from app.publishing.intro import build_intro
from app.publishing.models import PostDraft, TemplateMode
from app.publishing.render import render_post
from app.publishing.skills import extract_skills


class TemplateEngine:
    """Deterministic editorial post builder (LLM optional later)."""

    def build_draft(
        self,
        vacancy: Vacancy,
        *,
        city_name: str = "Нижний Новгород",
        score: VacancyScore | None = None,
        variant: int = 0,
        mode: TemplateMode | None = None,
    ) -> PostDraft:
        enriched = _enrich_sections(vacancy)
        skills = extract_skills(enriched)
        availability = assess_availability(enriched, skills=skills)
        editorial = build_editorial(
            enriched,
            availability,
            score,
            variant=variant,
        )
        resolved_mode = mode or choose_mode(
            availability,
            grade=editorial.grade if editorial else None,
        )
        title = _headline_title(enriched.title)
        company = (enriched.company_name or "").strip() or None
        if company and _looks_broken_company(company):
            company = None

        return PostDraft(
            title=title,
            company=company,
            salary=availability.salary_line,
            intro=build_intro(
                enriched,
                availability,
                city_name=city_name,
                variant=variant,
            ),
            meta=build_meta(
                enriched,
                availability,
                city_name=city_name,
            ),
            blocks=build_blocks(
                enriched,
                availability,
                mode=resolved_mode,
                variant=variant,
            ),
            editorial=editorial,
            source_url=enriched.source_url,
            mode=resolved_mode,
            variant=variant,
        )

    def render(self, draft: PostDraft) -> str:
        return render_post(draft)

    def generate(
        self,
        vacancy: Vacancy,
        *,
        city_name: str = "Нижний Новгород",
        score: VacancyScore | None = None,
        variant: int = 0,
        mode: TemplateMode | None = None,
    ) -> tuple[PostDraft, str]:
        draft = self.build_draft(
            vacancy,
            city_name=city_name,
            score=score,
            variant=variant,
            mode=mode,
        )
        return draft, self.render(draft)


def build_publication_preview(
    vacancy: Vacancy,
    *,
    city_name: str = "Нижний Новгород",
    score: VacancyScore | None = None,
    variant: int = 0,
) -> dict[str, Any]:
    engine = TemplateEngine()
    draft, text = engine.generate(
        vacancy,
        city_name=city_name,
        score=score,
        variant=variant,
    )
    return {
        "draft": draft.model_dump_structured(),
        "rendered_text": text,
        "mode": draft.mode.value,
        "variant": variant,
    }


def _enrich_sections(vacancy: Vacancy) -> Vacancy:
    """Split mixed blobs on the fly for vacancies parsed before section-split."""
    blob = vacancy.requirements if not vacancy.duties else None
    if not blob and vacancy.raw_text and (not vacancy.duties or not vacancy.benefits):
        blob = vacancy.raw_text
    if not blob:
        return vacancy
    merged = merge_sections(
        duties=vacancy.duties,
        requirements=vacancy.requirements,
        benefits=vacancy.benefits,
        blob=blob,
    )
    if (
        merged.duties == vacancy.duties
        and merged.requirements == vacancy.requirements
        and merged.benefits == vacancy.benefits
    ):
        return vacancy
    # Update fields used by the draft; session flush is caller's concern
    vacancy.duties = merged.duties or vacancy.duties
    vacancy.requirements = merged.requirements or vacancy.requirements
    vacancy.benefits = merged.benefits or vacancy.benefits
    return vacancy


def _headline_title(title: str | None) -> str:
    raw = (title or "Вакансия").strip()
    for prefix in ("Требуется ", "требуется ", "Вакансия: ", "вакансия: "):
        if raw.startswith(prefix):
            raw = raw[len(prefix) :]
    while raw and not (raw[0].isalnum() or raw[0] in "«\"("):
        raw = raw[1:].lstrip()
    return raw[:160] or "Вакансия"


def _looks_broken_company(name: str) -> bool:
    lowered = name.lower()
    if lowered.startswith((":", "отвечать", "http")):
        return True
    return len(name) < 2
