import json

import pytest

from app.sense.input.engine import INPUT_SENSE, INPUT_UNDERSTANDING
from app.sense.input.models import (
    DialectStatus,
    InputType,
    RecognitionStatus,
)


def test_basic_question():
    result = INPUT_SENSE.understand("What is happening with oil?")

    assert result.input_type == InputType.TEXT
    assert result.language == "en"
    assert result.is_question is True
    assert result.is_statement is False


def test_basic_statement():
    result = INPUT_SENSE.understand("Oil prices increased today.")

    assert result.is_statement is True
    assert result.is_question is False


def test_currency_percentage_and_number():
    result = INPUT_SENSE.understand("Gold is up 2.4% at $2,500.")

    assert "USD" in result.currencies
    assert result.percentages
    assert result.numbers


def test_multiple_currencies():
    result = INPUT_SENSE.understand("The company earned $2 million and ₦500 million.")

    assert "USD" in result.currencies
    assert "NGN" in result.currencies


def test_percentage_detection():
    result = INPUT_SENSE.understand("Revenue increased by 25%.")

    assert result.percentages
    assert result.percentages[0].percentage == 25.0


def test_decimal_number_detection():
    result = INPUT_SENSE.understand("The price is 1.0870.")

    assert result.numbers


def test_units_detection():
    result = INPUT_SENSE.understand(
        "Oil production reached 2.5 million barrels per day."
    )

    assert result.units


def test_date_detection():
    result = INPUT_SENSE.understand("Research oil on 2026-09-29.")

    assert result.dates


def test_multiple_date_formats():
    result = INPUT_SENSE.understand("Research the report from January 15, 2026.")

    assert result.dates


def test_url_detection():
    result = INPUT_SENSE.understand("Open https://example.com")

    assert len(result.urls) == 1
    assert result.urls[0].text == "https://example.com"


def test_abbreviation_detection():
    result = INPUT_SENSE.understand("What is GDP and CPI?")

    assert "GDP" in result.abbreviations
    assert "CPI" in result.abbreviations


def test_command_detection():
    result = INPUT_SENSE.understand("Run the analysis")

    assert result.is_command is True


def test_code_detection_for_function_definition():
    result = INPUT_SENSE.understand("def calculate_profit():")

    assert result.is_code is True


def test_input_type_text():
    result = INPUT_SENSE.understand(
        "Hello BAIG",
        input_type=InputType.TEXT,
    )

    assert result.input_type == InputType.TEXT


def test_input_type_market_data():
    result = INPUT_SENSE.understand(
        "Gold price data",
        input_type=InputType.MARKET_DATA,
    )

    assert result.input_type == InputType.MARKET_DATA


def test_input_type_news():
    result = INPUT_SENSE.understand(
        "Central bank announces new policy",
        input_type=InputType.NEWS,
    )

    assert result.input_type == InputType.NEWS


def test_input_type_api_data():
    result = INPUT_SENSE.understand(
        "API response received",
        input_type=InputType.API_DATA,
    )

    assert result.input_type == InputType.API_DATA


def test_input_type_document():
    result = INPUT_SENSE.understand(
        "Business report",
        input_type=InputType.DOCUMENT,
    )

    assert result.input_type == InputType.DOCUMENT


def test_input_type_pdf():
    result = INPUT_SENSE.understand(
        "Economic report",
        input_type=InputType.PDF,
    )

    assert result.input_type == InputType.PDF


def test_input_type_image():
    result = INPUT_SENSE.understand(
        "Chart screenshot",
        input_type=InputType.IMAGE,
    )

    assert result.input_type == InputType.IMAGE


def test_input_type_chart():
    result = INPUT_SENSE.understand(
        "Price chart",
        input_type=InputType.CHART,
    )

    assert result.input_type == InputType.CHART


def test_input_type_table():
    result = INPUT_SENSE.understand(
        "Revenue table",
        input_type=InputType.TABLE,
    )

    assert result.input_type == InputType.TABLE


def test_input_type_video_transcript():
    result = INPUT_SENSE.understand(
        "Video transcript",
        input_type=InputType.VIDEO_TRANSCRIPT,
    )

    assert result.input_type == InputType.VIDEO_TRANSCRIPT


def test_input_type_system_event():
    result = INPUT_SENSE.understand(
        "System event received",
        input_type=InputType.SYSTEM_EVENT,
    )

    assert result.input_type == InputType.SYSTEM_EVENT


def test_confidence_is_valid():
    result = INPUT_SENSE.understand("What is happening with oil?")

    assert 0.0 <= result.confidence <= 1.0


def test_empty_input_does_not_crash():
    result = INPUT_SENSE.understand("")

    assert result.raw_input == ""
    assert 0.0 <= result.confidence <= 1.0


def test_whitespace_input_does_not_crash():
    result = INPUT_SENSE.understand("   ")

    assert result.raw_input == "   "
    assert 0.0 <= result.confidence <= 1.0


def test_question_with_multiple_information_types():
    result = INPUT_SENSE.understand(
        "Why did oil rise 4.5% from $75 to $78 on 2026-09-29?"
    )

    assert result.is_question is True
    assert result.percentages
    assert result.numbers
    assert result.currencies
    assert result.dates


def test_normalization_preserves_raw_input():
    result = INPUT_UNDERSTANDING.understand("  Hello   BAIG  ")
    assert result.raw_input == "  Hello   BAIG  "
    assert result.normalized_text == "Hello BAIG"


def test_nfkc_normalization():
    result = INPUT_UNDERSTANDING.understand("＄500")
    assert result.normalized_text == "$500"


def test_scaled_currency():
    result = INPUT_UNDERSTANDING.understand("The company made $1.2B")
    assert any(c.code == "USD" for c in result.currencies)
    assert any(n.normalized_value == 1_200_000_000 for n in result.numbers)


def test_naira_currency():
    result = INPUT_UNDERSTANDING.understand("Revenue was ₦500m")
    assert any(c.code == "NGN" for c in result.currencies)
    assert any(n.normalized_value == 500_000_000 for n in result.numbers)


def test_basis_points():
    result = INPUT_UNDERSTANDING.understand("Rates increased by 25 bps")
    item = next(n for n in result.numbers if n.quantity_type == "basis_points")
    assert item.basis_points == 25
    assert item.normalized_value == 0.0025


def test_ratio():
    result = INPUT_UNDERSTANDING.understand("The return was 2.5x")
    item = next(n for n in result.numbers if n.quantity_type == "ratio")
    assert item.value == 2.5


def test_abbreviations():
    result = INPUT_UNDERSTANDING.understand("GDP, CPI and EBITDA are important.")
    detected = {a.text.upper() for a in result.abbreviations}
    assert {"GDP", "CPI", "EBITDA"} <= detected


def test_units():
    result = INPUT_UNDERSTANDING.understand("Oil production reached 2.0 mbpd.")
    assert any(u.normalized == "million barrels per day" for u in result.units)


def test_symbols():
    result = INPUT_UNDERSTANDING.understand("Profit increased +20%.")
    symbols = {s.text for s in result.symbols}
    assert "%" in symbols
    assert "+" in symbols


def test_multiple_urls():
    result = INPUT_UNDERSTANDING.understand(
        "Visit https://example.com and https://openai.com."
    )
    assert len(result.urls) == 2


def test_multiple_dates():
    result = INPUT_UNDERSTANDING.understand("Compare 2025-01-01 with January 15, 2026.")
    assert len(result.dates) >= 2


def test_code_detection_for_inline_function():
    result = INPUT_UNDERSTANDING.understand("def calculate(x): return x * 2")
    assert result.is_code is True


def test_command_detection_for_percentage_calculation():
    result = INPUT_UNDERSTANDING.understand("Calculate 20% of 500")
    assert result.is_command is True


def test_question_detection():
    result = INPUT_UNDERSTANDING.understand("What is the current GDP?")
    assert result.is_question is True


def test_empty_input():
    result = INPUT_UNDERSTANDING.understand("")
    assert result.raw_input == ""
    assert result.normalized_text == ""
    assert result.confidence == 1.0


def test_whitespace_input():
    result = INPUT_UNDERSTANDING.understand("   ")
    assert result.raw_input == "   "
    assert result.normalized_text == ""


def test_financial_numbers_together():
    result = INPUT_UNDERSTANDING.understand(
        "Revenue increased 20% from ₦500m to ₦600m."
    )

    assert any(n.quantity_type == "percentage" for n in result.numbers)
    assert any(c.code == "NGN" for c in result.currencies)
    assert len(result.numbers) >= 3


def test_input_type_is_preserved():
    result = INPUT_UNDERSTANDING.understand(
        "Gold price is rising",
        InputType.MARKET_DATA,
    )
    assert result.input_type == InputType.MARKET_DATA


def test_external_intelligence_flag_for_uncertain_language():
    result = INPUT_UNDERSTANDING.understand("Xyz qwerty blabla")
    assert result.requires_external_intelligence is True


@pytest.mark.parametrize(
    "input_type",
    [
        InputType.TEXT,
        InputType.VOICE_TRANSCRIPT,
        InputType.DOCUMENT,
        InputType.PDF,
        InputType.IMAGE,
        InputType.CHART,
        InputType.TABLE,
        InputType.VIDEO_TRANSCRIPT,
        InputType.API_DATA,
        InputType.MARKET_DATA,
        InputType.NEWS,
        InputType.WEBSITE_INFORMATION,
        InputType.SYSTEM_EVENT,
    ],
)
def test_every_supported_input_type_is_preserved(input_type):
    result = INPUT_UNDERSTANDING.understand(
        "Revenue increased 4%.",
        input_type=input_type,
    )

    assert result.input_type == input_type
    assert result.normalized_text == "Revenue increased 4%."


@pytest.mark.parametrize(
    "input_type",
    [
        InputType.DOCUMENT,
        InputType.PDF,
        InputType.IMAGE,
        InputType.CHART,
        InputType.TABLE,
        InputType.WEBSITE_INFORMATION,
    ],
)
def test_opaque_content_is_referenced_without_claiming_extraction(input_type):
    result = INPUT_UNDERSTANDING.understand(
        "",
        input_type=input_type,
        content_reference="asset://reports/quarterly-01",
        input_metadata={"asset_id": "quarterly-01", "page_count": 4},
    )

    assert result.input_type == input_type
    assert result.requires_content_extraction is True
    assert "does not extract content" in result.content_extraction_reason
    assert result.content_reference == "asset://reports/quarterly-01"
    assert result.input_metadata["page_count"] == 4
    assert result.normalized_text == ""
    assert result.numbers == ()
    assert result.dates == ()
    assert result.spans == ()


def test_spelling_and_slang_are_structured_with_provenance():
    text = "I gonna recieve the report, bro"
    result = INPUT_UNDERSTANDING.understand(text)

    assert result.spelling_errors_detected is True
    assert result.spelling_status == RecognitionStatus.DETECTED
    issue = next(
        issue
        for issue in result.spelling_issues
        if issue.suggested_correction == "receive"
    )
    spelling_span = next(span for span in result.spans if span.text == issue.text)
    assert text[spelling_span.start : spelling_span.end] == "recieve"
    assert any(mention.text == "gonna" for mention in result.slang_mentions)
    assert result.slang_status == RecognitionStatus.DETECTED
    assert all(
        issue.metadata.source.value == "local_rule" for issue in result.spelling_issues
    )
    assert any(span.span_type.value == "spelling" for span in result.spans)
    assert result.raw_input == text


def test_unknown_spelling_is_not_silently_corrected():
    text = "The market has a flarble pattern."
    result = INPUT_UNDERSTANDING.understand(text)

    assert result.raw_input == text
    assert result.normalized_text == text
    assert result.spelling_issues == ()
    assert result.spelling_status == RecognitionStatus.UNCERTAIN


def test_nigerian_pidgin_dialect_is_identified():
    result = INPUT_UNDERSTANDING.understand("Abeg, wetin dey happen?")

    assert result.language == "pcm"
    assert result.dialect == "Nigerian Pidgin"
    assert result.dialect_status == DialectStatus.DETECTED


@pytest.mark.parametrize(
    ("text", "language", "dialect"),
    [
        ("Hola, el precio del mercado aumentó.", "es", None),
        ("Bonjour, le prix du marché augmente.", "fr", None),
        ("The colour centre is changing.", "en", "British English"),
        ("The color center is changing.", "en", "American English"),
    ],
)
def test_common_languages_and_english_dialects(text, language, dialect):
    result = INPUT_UNDERSTANDING.understand(text)

    assert result.language == language
    assert result.dialect == dialect
    assert result.dialect_status == (
        DialectStatus.DETECTED if dialect is not None else DialectStatus.UNKNOWN
    )


def test_conflicting_english_dialect_signals_are_uncertain():
    result = INPUT_UNDERSTANDING.understand("The colour center is changing.")

    assert result.language == "en"
    assert result.dialect is None
    assert result.dialect_status == DialectStatus.UNCERTAIN
    assert result.requires_external_intelligence is True


def test_unsupported_dialect_is_not_classified():
    result = INPUT_UNDERSTANDING.understand("The lift is on holiday.")

    assert result.language == "en"
    assert result.dialect is None
    assert result.dialect_status == DialectStatus.UNKNOWN


def test_unknown_slang_is_not_given_an_invented_meaning():
    result = INPUT_UNDERSTANDING.understand("Market glorpmaxxing")

    assert all(item.text != "glorpmaxxing" for item in result.slang_mentions)
    assert all(item.meaning is None for item in result.slang_mentions)
    assert result.slang_status == RecognitionStatus.UNCERTAIN
    assert result.requires_external_intelligence is True


def test_weak_language_evidence_reduces_confidence_and_requests_intelligence():
    result = INPUT_UNDERSTANDING.understand("The colour market is lowkey bussin.")
    strong_result = INPUT_UNDERSTANDING.understand("The market price increased today.")

    assert result.language_status.value == "uncertain"
    assert result.confidence < 0.70
    assert result.confidence < strong_result.confidence
    assert result.requires_external_intelligence is True


def test_unknown_latin_language_is_not_guessed_as_english():
    result = INPUT_UNDERSTANDING.understand("Xyz qwerty blabla")

    assert result.language == "unknown"
    assert result.requires_external_intelligence is True


def test_unsupported_non_latin_language_is_not_guessed():
    result = INPUT_UNDERSTANDING.understand("مرحبا بكم في السوق")

    assert result.language in (None, "unknown")
    assert result.language_status.value == "unknown"
    assert result.requires_external_intelligence is True


def test_common_business_abbreviations_are_expanded():
    result = INPUT_UNDERSTANDING.understand("TTM FCF ARR MRR IPO ETF")

    expansions = {
        item.text.upper(): item.expanded_form for item in result.abbreviations
    }
    assert expansions["TTM"] == "Trailing Twelve Months"
    assert expansions["FCF"] == "Free Cash Flow"
    assert expansions["ARR"] == "Annual Recurring Revenue"
    assert expansions["MRR"] == "Monthly Recurring Revenue"
    assert expansions["IPO"] == "Initial Public Offering"
    assert expansions["ETF"] == "Exchange-Traded Fund"


def test_common_english_words_do_not_become_pidgin_slang():
    result = INPUT_UNDERSTANDING.understand("We go to the market and make money.")

    assert not {item.text for item in result.slang_mentions} & {"go", "make"}


def test_signed_scaled_locale_and_financial_numbers():
    result = INPUT_UNDERSTANDING.understand(
        "Move -1,234.50 to +2.5m, add 3 billion and record (500)."
    )

    values = [number.normalized_value for number in result.numbers]
    assert -1234.5 in values
    assert 2_500_000 in values
    assert 3_000_000_000 in values
    assert -500 in values

    localized = INPUT_UNDERSTANDING.understand("The price is 1.234,56 EUR.")
    assert any(number.value == 1234.56 for number in localized.numbers)
    assert any(number.currency == "EUR" for number in localized.numbers)


def test_scaled_number_words_percentages_ratios_and_basis_points():
    result = INPUT_UNDERSTANDING.understand(
        "1 thousand, 2 million, 3 billion, 4 trillion, 12 percent, -2.3x and -25 basis points"
    )

    normalized_values = {number.normalized_value for number in result.numbers}
    assert {1_000, 2_000_000, 3_000_000_000, 4_000_000_000_000} <= normalized_values
    assert any(number.percentage == 12 for number in result.percentages)
    assert any(number.ratio == -2.3 for number in result.numbers)
    assert any(number.basis_points == -25 for number in result.numbers)


def test_multiple_currency_formats_and_currency_association():
    result = INPUT_UNDERSTANDING.understand("$1,200 USD, EUR 2.5m, ₦500m and 750 GBP")

    codes = {currency.code for currency in result.currencies}
    assert {"USD", "EUR", "NGN", "GBP"} <= codes
    assert {number.currency for number in result.numbers} >= {
        "USD",
        "EUR",
        "NGN",
        "GBP",
    }


def test_units_and_symbols_include_common_scientific_and_financial_forms():
    result = INPUT_UNDERSTANDING.understand(
        "Output reached 50 MW in 2 hours, applied 5 mg, ±3%."
    )

    assert any(unit.normalized == "MW" for unit in result.units)
    assert any(unit.normalized == "hour" for unit in result.units)
    assert any(unit.normalized == "mg" for unit in result.units)
    assert any(symbol.text == "±" for symbol in result.symbols)


def test_additional_currency_symbols_have_currency_and_numeric_meanings():
    result = INPUT_UNDERSTANDING.understand("₽100, ₩2000, ฿50 and ¢25")

    assert {item.code for item in result.currencies} >= {"RUB", "KRW", "THB", "USD"}
    assert {item.currency for item in result.numbers} >= {"RUB", "KRW", "THB", "USD"}


def test_dates_relative_dates_and_date_number_isolation():
    result = INPUT_UNDERSTANDING.understand(
        "Compare 2026-09-29, 09/30/2026, January 15, 2026, yesterday and in 3 days."
    )

    assert len(result.dates) == 5
    assert all(date.temporal_type in {"absolute", "relative"} for date in result.dates)
    assert any(date.normalized == "2026-09-29" for date in result.dates)
    assert any(
        date.text == "in 3 days" and date.temporal_type == "relative"
        for date in result.dates
    )
    assert not any(number.text == "3" for number in result.numbers)


def test_ambiguous_numeric_date_is_reported_without_locale_guessing():
    result = INPUT_UNDERSTANDING.understand("The report date is 03/04/2026.")

    assert result.ambiguous is True
    assert result.dates[0].normalized is None
    assert result.dates[0].temporal_type == "ambiguous"
    assert result.ambiguity_reason


def test_dates_and_numeric_urls_do_not_leak_digits_as_numbers():
    result = INPUT_UNDERSTANDING.understand(
        "Visit https://example.com/report/2026/09/29; event date 2026-09-29; value 42."
    )

    assert len(result.urls) == 1
    assert len(result.dates) == 1
    assert [number.value for number in result.numbers] == [42]


def test_question_detection_ignores_interrogative_words_in_statements():
    result = INPUT_UNDERSTANDING.understand(
        "The report explains what changed and when prices moved."
    )

    assert result.is_question is False
    assert result.is_statement is True


def test_command_detection_ignores_verb_led_statements():
    result = INPUT_UNDERSTANDING.understand("Run rates were high last quarter.")

    assert result.is_command is False
    assert result.is_statement is True


def test_code_detection_does_not_treat_punctuation_as_code():
    result = INPUT_UNDERSTANDING.understand(
        "The report compares growth; the result is stable (see table 2)."
    )

    assert result.is_code is False
    assert result.is_statement is True


def test_code_assignment_is_detected():
    result = INPUT_UNDERSTANDING.understand("profit = revenue - cost")

    assert result.is_code is True
    assert any(span.span_type.value == "code" for span in result.spans)


def test_repeated_span_locations_point_to_distinct_occurrences():
    text = "Revenue rose 5% and revenue rose 5%."
    result = INPUT_UNDERSTANDING.understand(text)
    percent_spans = [span for span in result.spans if span.text == "5%"]

    assert len(percent_spans) == 2
    assert [text[span.start : span.end] for span in percent_spans] == ["5%", "5%"]
    assert percent_spans[0].start != percent_spans[1].start


def test_unusual_unicode_and_punctuation_are_safe():
    raw = "\ufeff  ＄５００ — café؟ 📈  "
    result = INPUT_UNDERSTANDING.understand(raw)

    assert result.raw_input == raw
    assert "$500" in result.normalized_text
    assert result.numbers
    assert 0.0 <= result.confidence <= 1.0


def test_result_metadata_and_public_fields_match_runtime_objects():
    result = INPUT_UNDERSTANDING.understand("GDP rose 3% to $100m.")
    serialized = result.to_dict()

    assert result.confidence_level.value
    assert result.metadata.confidence == result.confidence
    assert result.abbreviations and hasattr(result.abbreviations[0], "expanded_form")
    assert result.currencies and hasattr(result.currencies[0], "code")
    assert result.units == result.unit_mentions
    assert result.symbols == result.symbol_mentions
    assert json.loads(json.dumps(serialized))["input_type"] == "text"


def test_input_type_string_is_normalized_to_enum():
    result = INPUT_UNDERSTANDING.understand("payload", input_type="market_data")

    assert result.input_type is InputType.MARKET_DATA


def test_numeric_only_input_has_confident_structural_understanding():
    result = INPUT_UNDERSTANDING.understand("1,250.75")

    assert result.language_status.value == "unknown"
    assert result.numbers[0].value == 1250.75
    assert result.confidence == 1.0
    assert result.requires_external_intelligence is False
