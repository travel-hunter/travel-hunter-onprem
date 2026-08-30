from email.message import EmailMessage

import pytest

from app.core.config import settings
from app.services import email as email_service


@pytest.fixture(autouse=True)
def configured_smtp():
    original_values = {
        "smtp_host": settings.smtp_host,
        "smtp_port": settings.smtp_port,
        "smtp_username": settings.smtp_username,
        "smtp_password": settings.smtp_password,
        "smtp_from_email": settings.smtp_from_email,
        "smtp_use_tls": settings.smtp_use_tls,
    }
    object.__setattr__(settings, "smtp_host", "smtp.example.test")
    object.__setattr__(settings, "smtp_port", 587)
    object.__setattr__(settings, "smtp_username", "")
    object.__setattr__(settings, "smtp_password", "")
    object.__setattr__(settings, "smtp_from_email", "no-reply@example.test")
    object.__setattr__(settings, "smtp_use_tls", True)
    yield
    for name, value in original_values.items():
        object.__setattr__(settings, name, value)


def capture_sent_message(monkeypatch) -> list[EmailMessage]:
    sent_messages: list[EmailMessage] = []
    monkeypatch.setattr(email_service, "_send_message", sent_messages.append)
    return sent_messages


def assert_link_email(
    message: EmailMessage,
    *,
    subject: str,
    to_email: str,
    url: str,
    button_label: str,
) -> None:
    assert message["Subject"] == subject
    assert message["From"] == "no-reply@example.test"
    assert message["To"] == to_email
    assert message.is_multipart()

    text_body = message.get_body(preferencelist=("plain",))
    html_body = message.get_body(preferencelist=("html",))
    assert text_body is not None
    assert html_body is not None
    assert url in text_body.get_content()

    html_content = html_body.get_content()
    assert f'href="{url}"' in html_content
    assert button_label in html_content
    assert "버튼이 열리지 않으면" in html_content


def test_signup_verification_email_includes_clickable_html_link(monkeypatch) -> None:
    sent_messages = capture_sent_message(monkeypatch)
    verify_url = "https://dev.travel-hunter.co.kr/signup/verify?token=signup-token"

    email_service.send_signup_verification_email(
        to_email="new@example.com",
        verify_url=verify_url,
    )

    assert len(sent_messages) == 1
    assert_link_email(
        sent_messages[0],
        subject="Travel Hunter 이메일 인증",
        to_email="new@example.com",
        url=verify_url,
        button_label="이메일 인증하고 가입 계속하기",
    )


def test_password_reset_email_includes_clickable_html_link(monkeypatch) -> None:
    sent_messages = capture_sent_message(monkeypatch)
    reset_url = "https://dev.travel-hunter.co.kr/reset-password?token=reset-token"

    email_service.send_password_reset_email(
        to_email="user@example.com",
        reset_url=reset_url,
    )

    assert len(sent_messages) == 1
    assert_link_email(
        sent_messages[0],
        subject="Travel Hunter 비밀번호 재설정",
        to_email="user@example.com",
        url=reset_url,
        button_label="비밀번호 재설정하기",
    )


def test_trip_invite_email_includes_clickable_html_link(monkeypatch) -> None:
    sent_messages = capture_sent_message(monkeypatch)
    invite_url = "https://dev.travel-hunter.co.kr/invites/invite-token/accept"

    email_service.send_trip_invite_email(
        to_email="friend@example.com",
        invite_url=invite_url,
    )

    assert len(sent_messages) == 1
    assert_link_email(
        sent_messages[0],
        subject="트래블헌터 일정 초대입니다",
        to_email="friend@example.com",
        url=invite_url,
        button_label="일정 초대 확인하기",
    )
