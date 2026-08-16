from decimal import Decimal
from unittest.mock import MagicMock

from google.genai.errors import ClientError

import app.services.forecast_chat as forecast_chat_module
from app.services.forecast_chat import (
    build_forecast_context,
    format_quantity,
)


def test_format_quantity_strips_trailing_zeros():
    assert format_quantity(Decimal("8.0000")) == "8"
    assert format_quantity(Decimal("3.0000")) == "3"
    assert format_quantity(Decimal("8.5000")) == "8.5"
    assert format_quantity(Decimal("8.2500")) == "8.25"


def test_format_quantity_zero_and_large_whole_numbers():
    assert format_quantity(Decimal("0.0000")) == "0"
    assert format_quantity(Decimal("100.0000")) == "100"
    assert (
        format_quantity(Decimal("69744.0000")) == "69744"
    )


def test_build_forecast_context_omits_trailing_zeros(
    db,
    test_products,
):
    context = build_forecast_context(db)

    assert ".0000" not in context


def test_forecast_chat_requires_auth(unauthenticated_client):
    response = unauthenticated_client.post(
        "/api/forecast/chat",
        json={"message": "What is the forecast?"},
    )

    assert response.status_code == 401


def test_forecast_chat_rejects_empty_message(client):
    response = client.post(
        "/api/forecast/chat",
        json={"message": ""},
    )

    assert response.status_code == 422


def test_forecast_chat_missing_api_key_returns_503(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        forecast_chat_module,
        "GEMINI_API_KEY",
        None,
    )

    response = client.post(
        "/api/forecast/chat",
        json={"message": "What is the forecast?"},
    )

    assert response.status_code == 503


def test_build_forecast_context_includes_real_product_data(
    db,
    test_products,
):
    context = build_forecast_context(db)

    assert "Forecast period: NEXT_CYCLE" in context

    for product in test_products:
        assert product.name in context


def test_forecast_chat_success_uses_forecast_context(
    client,
    monkeypatch,
    test_products,
):
    mock_response = MagicMock()
    mock_response.text = "Here is your forecast summary."

    mock_client_instance = MagicMock()
    mock_client_instance.models.generate_content.return_value = (
        mock_response
    )

    monkeypatch.setattr(
        forecast_chat_module,
        "GEMINI_API_KEY",
        "fake-key-for-test",
    )
    monkeypatch.setattr(
        forecast_chat_module.genai,
        "Client",
        MagicMock(return_value=mock_client_instance),
    )

    response = client.post(
        "/api/forecast/chat",
        json={"message": "Summarize the forecast"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "reply": "Here is your forecast summary."
    }

    call_kwargs = (
        mock_client_instance.models.generate_content.call_args.kwargs
    )

    assert test_products[0].name in call_kwargs["contents"]
    assert "Summarize the forecast" in call_kwargs["contents"]


def test_forecast_chat_empty_ai_response_returns_503(
    client,
    monkeypatch,
):
    mock_response = MagicMock()
    mock_response.text = ""

    mock_client_instance = MagicMock()
    mock_client_instance.models.generate_content.return_value = (
        mock_response
    )

    monkeypatch.setattr(
        forecast_chat_module,
        "GEMINI_API_KEY",
        "fake-key-for-test",
    )
    monkeypatch.setattr(
        forecast_chat_module.genai,
        "Client",
        MagicMock(return_value=mock_client_instance),
    )

    response = client.post(
        "/api/forecast/chat",
        json={"message": "hi"},
    )

    assert response.status_code == 503


def test_forecast_chat_upstream_api_error_returns_502(
    client,
    monkeypatch,
):
    mock_client_instance = MagicMock()
    mock_client_instance.models.generate_content.side_effect = (
        ClientError(
            400,
            {
                "error": {
                    "message": "API key not valid.",
                    "status": "INVALID_ARGUMENT",
                }
            },
        )
    )

    monkeypatch.setattr(
        forecast_chat_module,
        "GEMINI_API_KEY",
        "fake-key-for-test",
    )
    monkeypatch.setattr(
        forecast_chat_module.genai,
        "Client",
        MagicMock(return_value=mock_client_instance),
    )

    response = client.post(
        "/api/forecast/chat",
        json={"message": "hi"},
    )

    assert response.status_code == 502
