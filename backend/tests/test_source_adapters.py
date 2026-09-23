"""Unit tests for SuperJob and TrudVsem SourceAdapters (no live HTTP)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from app.core.config import Settings
from app.sources.superjob import SuperJobSourceAdapter
from app.sources.trudvsem import TrudVsemSourceAdapter


class _FakeHttp:
    def __init__(self, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
        self.payloads = payload if isinstance(payload, list) else [payload]
        self.calls: list[tuple[str, dict[str, Any] | None]] = []
        self._i = 0

    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        self.calls.append((url, params))
        idx = min(self._i, len(self.payloads) - 1)
        self._i += 1
        return self.payloads[idx]


@pytest.mark.asyncio
async def test_superjob_fetches_by_date_not_payment() -> None:
    settings = Settings(
        superjob_secret_key="test-secret",
        superjob_vacancies_per_run=10,
    )
    http = _FakeHttp(
        {
            "objects": [
                {
                    "id": 101,
                    "profession": "Аналитик данных",
                    "firm_name": "ООО Тест",
                    "payment_from": 120000,
                    "payment_to": 150000,
                    "currency": "rub",
                    "date_published": int(datetime(2026, 9, 22, tzinfo=UTC).timestamp()),
                    "candidat": "SQL, Python",
                    "work": "Аналитика витрин",
                    "experience": {"title": "От 1 года"},
                    "type_of_work": {"title": "Полная занятость"},
                    "place_of_work": {"title": "На месте работодателя"},
                    "link": "https://www.superjob.ru/vakansii/101.html",
                    "town": {"id": 1, "title": "Нижний Новгород"},
                },
                {
                    "id": 102,
                    "profession": "Курьер",
                    "firm_name": "Доставка",
                    "payment_from": 80000,
                    "payment_to": 0,
                    "currency": "rub",
                    "date_published": int(datetime(2026, 9, 22, tzinfo=UTC).timestamp()),
                    "candidat": "",
                    "work": "",
                    "experience": {"title": "Без опыта"},
                    "type_of_work": {"title": "Подработка"},
                    "place_of_work": {"title": "Разъездной"},
                    "link": "https://www.superjob.ru/vakansii/102.html",
                    "town": {"id": 1, "title": "Нижний Новгород"},
                },
            ]
        }
    )
    adapter = SuperJobSourceAdapter(
        settings=settings,
        town="Нижний Новгород",
        keywords=[""],
        http_client=http,  # type: ignore[arg-type]
    )
    items = await adapter.fetch_new_items()
    assert len(items) == 1
    assert items[0].source_item_id == "101"
    assert items[0].raw_payload["name"] == "Аналитик данных"
    assert http.calls
    assert http.calls[0][1] is not None
    assert http.calls[0][1]["order_field"] == "date"


@pytest.mark.asyncio
async def test_superjob_uses_incremental_published_from() -> None:
    settings = Settings(superjob_secret_key="test-secret", superjob_vacancies_per_run=5)
    http = _FakeHttp({"objects": []})
    cursor = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
    adapter = SuperJobSourceAdapter(
        settings=settings,
        town="Нижний Новгород",
        last_timestamp=cursor,
        keywords=[""],
        http_client=http,  # type: ignore[arg-type]
    )
    await adapter.fetch_new_items()
    params = http.calls[0][1]
    assert params is not None
    assert "date_published_from" in params
    assert "period" not in params


@pytest.mark.asyncio
async def test_trudvsem_paginates_and_keeps_dates() -> None:
    settings = Settings(trudvsem_max_pages=5)
    page0 = {
        "meta": {"total": 150, "limit": 100},
        "results": {
            "vacancies": [
                {
                    "vacancy": {
                        "id": "aaa",
                        "job-name": "Инженер-конструктор",
                        "company": {"name": "Завод", "inn": "123"},
                        "salary_min": 90000,
                        "salary_max": 120000,
                        "duty": "Проектирование узлов",
                        "schedule": "5/2",
                        "creation-date": "2026-09-01",
                        "date_modify": "2026-09-22T10:00:00+0300",
                        "vac_url": "https://trudvsem.ru/vacancy/card/1/aaa",
                        "requirement": {"experience": 3, "education": "Высшее"},
                        "category": {"specialisation": "Инженерия"},
                        "addresses": {
                            "address": [{"location": "г Нижний Новгород, ул Ленина, 1"}]
                        },
                        "contact_list": [{"contact_type": "Телефон", "contact_value": "+7900"}],
                    }
                }
            ]
        },
    }
    page1 = {"meta": {"total": 150, "limit": 100}, "results": {"vacancies": []}}
    http = _FakeHttp([page0, page1])
    adapter = TrudVsemSourceAdapter(
        settings=settings,
        region_code="52",
        modified_from=None,
        http_client=http,  # type: ignore[arg-type]
    )
    items = await adapter.fetch_new_items()
    assert len(items) == 1
    assert items[0].source_item_id == "aaa"
    assert items[0].source_url and "trudvsem.ru" in items[0].source_url
    assert items[0].raw_payload["creation_date"]
    assert items[0].raw_payload["date_modify"]
    assert http.calls[0][1] is not None
    assert http.calls[0][1]["limit"] == 100
    assert "modifiedFrom" not in http.calls[0][1]


@pytest.mark.asyncio
async def test_trudvsem_incremental_modified_from() -> None:
    settings = Settings(trudvsem_max_pages=2)
    http = _FakeHttp({"meta": {"total": 0, "limit": 100}, "results": {"vacancies": []}})
    adapter = TrudVsemSourceAdapter(
        settings=settings,
        region_code="52",
        modified_from=datetime(2026, 9, 21, tzinfo=UTC),
        http_client=http,  # type: ignore[arg-type]
    )
    await adapter.fetch_new_items()
    params = http.calls[0][1]
    assert params is not None
    assert params["modifiedFrom"] == "2026-09-21T00:00:00Z"


@pytest.mark.asyncio
async def test_trudvsem_requires_region_code() -> None:
    settings = Settings()
    with pytest.raises(RuntimeError, match="trudvsem_region_code_missing"):
        TrudVsemSourceAdapter(settings=settings, region_code="  ")


@pytest.mark.asyncio
async def test_superjob_requires_secret() -> None:
    settings = Settings(superjob_secret_key=None)
    with pytest.raises(RuntimeError, match="superjob_secret_missing"):
        SuperJobSourceAdapter(settings=settings, town="Нижний Новгород")
