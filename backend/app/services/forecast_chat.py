import os
from decimal import Decimal

from dotenv import load_dotenv
from google import genai
from sqlalchemy.orm import Session

from app.services.forecasting import get_forecast

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Configurable so a model rename/deprecation (Google has already
# retired two model names since this integration was first built)
# only requires an env change, not a code change. Defaults to the
# currently verified-working model - not mandatory like GEMINI_API_KEY,
# since a sensible default keeps the feature usable without every
# environment having to set this explicitly.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "Gemini 3 Flash")


class ChatConfigurationError(Exception):
    """Raised when the chat feature isn't usable (missing/invalid key config)."""


def format_quantity(value: Decimal) -> str:
    """
    Trims a Decimal's stored trailing zeros for display only - e.g.
    Decimal("8.0000") -> "8", Decimal("8.2500") -> "8.25". Purely
    presentational: the underlying stored/returned Decimal values
    (Numeric(12,4) columns, GET /api/forecast's response) are
    untouched by this - only the plain-text context string handed to
    Gemini uses it, so the assistant echoes "8 units" instead of
    "8.0000 units" without changing any API contract or calculation.
    Whole numbers are handled via to_integral_value() rather than
    Decimal.normalize() alone, which can fall back to scientific
    notation (e.g. "1E+2") for values like 100 - not appropriate for
    a quantity/percentage shown to a person.
    """

    if value == value.to_integral_value():
        return str(value.to_integral_value())

    return str(value.normalize())


def build_forecast_context(db: Session) -> str:
    """
    Plain-text summary of the same data GET /api/forecast already
    returns - the chatbot's context is scoped to forecast data only
    (approved scope, not the whole business). Reuses get_forecast()
    directly rather than recomputing anything: historical demand,
    predicted demand, trend, confidence, and status all come from the
    existing, already-tested forecast algorithm - never duplicated
    here. The chatbot never queries the database directly.
    """

    forecast = get_forecast(db)

    lines = [
        f"Forecast period: {forecast['forecast_period']}",
        "",
        "Per-product forecast:",
    ]

    for product in forecast["products"]:
        historical_quantity = format_quantity(
            product["historical_quantity"]
        )
        forecast_quantity = format_quantity(
            product["forecast_quantity"]
        )
        confidence_level = format_quantity(
            product["confidence_level"]
        )

        lines.append(
            f"- {product['product_name']}: historical demand "
            f"{historical_quantity} units, predicted "
            f"demand {forecast_quantity} units, trend "
            f"{product['trend']}, confidence "
            f"{confidence_level}%, status "
            f"{product['forecast_status']}"
        )

    return "\n".join(lines)


SYSTEM_PROMPT = (
    "You are a demand forecasting assistant for a furniture "
    "manufacturing business. Answer the user's question using ONLY "
    "the forecast data provided below - never invent numbers that "
    "aren't present in it. If the data doesn't contain what's needed "
    "to answer, say so plainly instead of guessing. Keep answers "
    "concise."
)


def generate_chat_reply(db: Session, message: str) -> str:
    """
    Builds the forecast context, sends it plus the user's message to
    Gemini, and returns the reply text. Raises ChatConfigurationError
    for local configuration problems (missing key, empty response) -
    callers distinguish that from upstream API errors
    (google.genai.errors.APIError), which are left to propagate as-is.
    """

    if not GEMINI_API_KEY:
        raise ChatConfigurationError(
            "GEMINI_API_KEY is not configured"
        )

    context = build_forecast_context(db)

    prompt = (
        f"{SYSTEM_PROMPT}\n\n{context}\n\nUser question: {message}"
    )

    client = genai.Client(api_key=GEMINI_API_KEY)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )

    if not response.text:
        raise ChatConfigurationError(
            "Empty response from AI service"
        )

    return response.text
