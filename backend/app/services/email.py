import os

from dotenv import load_dotenv

load_dotenv()

# No email provider (SMTP, SendGrid, etc.) exists anywhere in this
# project - confirmed by inspection before adding this feature. Real
# delivery is intentionally NOT faked here. FRONTEND_URL builds the
# link the user would click; EMAIL_PROVIDER selects the transport -
# "console" (default, dev-safe) logs the reset link instead of
# sending it. Wiring an actual provider means adding a branch here
# that reads its own credentials from environment variables (never
# hardcoded) - e.g. SMTP_HOST/SMTP_PORT/SMTP_USERNAME/SMTP_PASSWORD -
# and is out of scope until a real provider is chosen.
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "console")


def build_reset_url(raw_token: str) -> str:
    return f"{FRONTEND_URL}/reset-password?token={raw_token}"


def send_password_reset_email(email: str, reset_url: str) -> None:
    """
    Dev-safe stand-in for real email delivery. Never returns or
    exposes the reset URL/token to the API caller - this is purely a
    server-side side effect, read from the backend's own console/log
    output during local development. Must be replaced with a real
    provider integration before any production use; the interface
    (email, reset_url) is deliberately provider-agnostic so that swap
    doesn't require touching any caller.
    """

    if EMAIL_PROVIDER == "console":
        # print(), not logger.info() - the app never configures a
        # logging level (Python's default root logger drops INFO),
        # so logger.info() here would silently vanish. print() always
        # reaches the console regardless of logging config, which
        # matters since this is the only way to retrieve the reset
        # link in dev.
        print(
            "\n[DEV EMAIL] Password reset requested for "
            f"{email}\n"
            f"Password reset URL: {reset_url}\n"
            "This link is only printed because EMAIL_PROVIDER=console "
            "(the default) - no real email provider is configured. "
            "Set EMAIL_PROVIDER to a real transport before production use.\n"
        )
        return

    raise RuntimeError(
        f"EMAIL_PROVIDER={EMAIL_PROVIDER!r} is not implemented. "
        "No email provider is currently integrated in this project."
    )
