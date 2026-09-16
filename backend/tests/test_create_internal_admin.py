from app.scripts.create_internal_admin import is_internal_admin_identifier


def test_internal_admin_identifier_requires_a_non_deliverable_domain() -> None:
    assert is_internal_admin_identifier("operator@travel-hunter.invalid")
    assert not is_internal_admin_identifier("operator@example.com")
    assert not is_internal_admin_identifier("operator.invalid")