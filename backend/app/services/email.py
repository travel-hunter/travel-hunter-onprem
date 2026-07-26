from __future__ import annotations

from html import escape
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


def _set_link_email_content(
    message: EmailMessage,
    *,
    intro_lines: list[str],
    button_label: str,
    url: str,
    fallback_label: str,
    outro_lines: list[str],
) -> None:
    text_lines = [
        *intro_lines,
        "",
        fallback_label,
        url,
        "",
        *outro_lines,
    ]
    message.set_content("\n".join(text_lines))

    escaped_url = escape(url, quote=True)
    escaped_button_label = escape(button_label)
    escaped_intro = "\n".join(f"<p>{escape(line)}</p>" for line in intro_lines if line)
    escaped_outro = "\n".join(f"<p>{escape(line)}</p>" for line in outro_lines if line)
    html_body = f"""\
<!doctype html>
<html lang="ko">
  <body style="margin:0;padding:24px;background:#f6f8fb;font-family:Arial,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:#172033;">
    <main style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:16px;padding:28px;border:1px solid #e6ebf2;">
      {escaped_intro}
      <p style="margin:28px 0;">
        <a href="{escaped_url}" style="display:inline-block;padding:14px 18px;border-radius:12px;background:#2563eb;color:#ffffff;text-decoration:none;font-weight:700;">
          {escaped_button_label}
        </a>
      </p>
      <p style="color:#5d6b82;">버튼이 열리지 않으면 아래 주소를 복사해 브라우저에 붙여넣어 주세요.</p>
      <p style="word-break:break-all;"><a href="{escaped_url}" style="color:#2563eb;">{escaped_url}</a></p>
      {escaped_outro}
    </main>
  </body>
</html>
"""
    message.add_alternative(html_body, subtype="html")


def send_password_reset_email(*, to_email: str, reset_url: str) -> None:
    _require_smtp_config()
    message = EmailMessage()
    message["Subject"] = "Travel Hunter 비밀번호 재설정"
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    _set_link_email_content(
        message,
        intro_lines=[
            "Travel Hunter 비밀번호 재설정을 요청하셨습니다.",
            "아래 버튼에서 30분 안에 새 비밀번호를 설정해 주세요.",
        ],
        button_label="비밀번호 재설정하기",
        url=reset_url,
        fallback_label="비밀번호 재설정 링크:",
        outro_lines=["요청하지 않았다면 이 메일을 무시해 주세요."],
    )

    _send_message(message)


def send_signup_verification_email(*, to_email: str, verify_url: str) -> None:
    _require_smtp_config()
    message = EmailMessage()
    message["Subject"] = "Travel Hunter 이메일 인증"
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    _set_link_email_content(
        message,
        intro_lines=[
            "Travel Hunter 회원가입 이메일 인증을 요청하셨습니다.",
            "아래 버튼에서 30분 안에 이메일 인증을 완료하고 비밀번호를 설정해 주세요.",
        ],
        button_label="이메일 인증하고 가입 계속하기",
        url=verify_url,
        fallback_label="이메일 인증 링크:",
        outro_lines=["요청하지 않았다면 이 메일을 무시해 주세요."],
    )

    _send_message(message)


def send_trip_invite_email(*, to_email: str, invite_url: str) -> None:
    _require_smtp_config()
    message = EmailMessage()
    message["Subject"] = "트래블헌터 일정 초대입니다"
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    _set_link_email_content(
        message,
        intro_lines=[
            "트래블헌터 일정 초대입니다.",
            "일정 상세 내용은 로그인 또는 회원가입 후 초대를 수락한 뒤 확인할 수 있습니다.",
            "아래 버튼에서 로그인 또는 회원가입 후 초대를 수락해 주세요.",
        ],
        button_label="일정 초대 확인하기",
        url=invite_url,
        fallback_label="일정 초대 링크:",
        outro_lines=["초대가 만료됐으면 초대한 사람에게 새 초대 링크를 요청하세요."],
    )

    _send_message(message)
