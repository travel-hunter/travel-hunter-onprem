from datetime import date, datetime

from app.services.travelmonth_collection import (
    TRAVELMONTH_REGIONAL_BENEFIT_URL,
    collect_regional_benefits_from_html,
)


class FakeDb:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1


def test_regional_benefit_source_url_uses_vacation_benefit_page() -> None:
    assert (
        TRAVELMONTH_REGIONAL_BENEFIT_URL
        == "https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do"
    )


def test_collect_regional_benefits_from_html_parses_and_upserts(monkeypatch) -> None:
    captured = {}

    def fake_upsert(db, sources):
        source_list = list(sources)
        captured["db"] = db
        captured["sources"] = source_list
        return source_list

    def fake_promote(db):
        captured["promoted_db"] = db

    monkeypatch.setattr(
        "app.services.travelmonth_collection.external_source_repository.upsert_external_source_records",
        fake_upsert,
    )
    monkeypatch.setattr(
        "app.services.travelmonth_collection.policy_normalization.promote_external_benefits_to_policies",
        fake_promote,
    )

    html = """
    <section data-benefit-item>
      <p class="organizer">강원특별자치도, 영월군</p>
      <h3>동강사진박물관 여행가는 달 입장료 최대 50% 할인</h3>
      <ul class="tags"><li>#사진관</li></ul>
      <p class="period">2026-04-01 ~ 2026-05-31</p>
      <p class="status">[진행중]</p>
      <div class="benefit">입장료 50% 할인</div>
      <p class="contact">1577-0545</p>
    </section>
    """

    db = FakeDb()
    result = collect_regional_benefits_from_html(
        db,
        html,
        fetched_at=datetime(2026, 5, 21, 9, 0, 0),
        today=date(2026, 5, 21),
    )

    assert captured["db"] is db
    assert captured["promoted_db"] is db
    assert len(captured["sources"]) == 1
    assert result.created_or_updated_count == 1
    assert result.source_name == "여행가는 달"
    assert db.commits == 1
