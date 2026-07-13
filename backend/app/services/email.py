from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import settings


class EmailDeliveryError(Exception):
    pass


class EmailNotConfiguredError(EmailDeliveryError):
    pass


def _require_smtp_config() -> None:
    if not settings.smtp_host or not settings.smtp_from_email:
        raise EmailNotConfiguredError("Email delivery is not configured")


def _send_message(message: EmailMessage) -> None:
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username or settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except Exception as error:
        raise EmailDeliveryError("Email delivery failed") from error


def send_password_reset_email(*, to_email: str, reset_url: str) -> None:
    _require_smtp_config()
    message = EmailMessage()
    message["Subject"] = "Travel Hunter 비밀번호 재설정"
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    message.set_content(
        "\n".join(
            [
                "Travel Hunter 비밀번호 재설정을 요청하셨습니다.",
                "",
                f"아래 링크에서 30분 안에 새 비밀번호를 설정해 주세요.",
                reset_url,
                "",
                "요청하지 않았다면 이 메일을 무시해 주세요.",
            ]
        )
    )

    _send_message(message)


def send_signup_verification_email(*, to_email: str, verify_url: str) -> None:
    _require_smtp_config()
    message = EmailMessage()
    message["Subject"] = "Travel Hunter 이메일 인증"
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    message.set_content(
        "\n".join(
            [
                "Travel Hunter 회원가입 이메일 인증을 요청하셨습니다.",
                "",
                "아래 링크에서 30분 안에 이메일 인증을 완료하고 비밀번호를 설정해 주세요.",
                verify_url,
                "",
                "요청하지 않았다면 이 메일을 무시해 주세요.",
            ]
        )
    )

    _send_message(message)


def send_trip_invite_email(*, to_email: str, invite_url: str) -> None:
    _require_smtp_config()
    message = EmailMessage()
    message["Subject"] = "트래블헌터 일정 초대입니다"
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    message.set_content(
        "\n".join(
            [
                "트래블헌터 일정 초대입니다.",
                "",
                "일정 상세 내용은 로그인 또는 회원가입 후 초대를 수락한 뒤 확인할 수 있습니다.",
                "아래 링크에서 로그인 또는 회원가입 후 수락해 주세요.",
                invite_url,
                "",
                "초대가 만료됐으면 초대한 사람에게 새 초대 링크를 요청하세요.",
            ]
        )
    )

    _send_message(message)
