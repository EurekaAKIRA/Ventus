"""Quality gates for LLM-generated assertion candidates."""

from __future__ import annotations

from case_generation.assertion_llm import (
    _is_json_content_type_assertion,
    _is_json_content_type_exact_assertion,
    _missing_required_expected,
    _repair_or_reject_llm_source,
    _is_unsafe_llm_header_assertion,
)


def test_llm_status_assertion_is_rejected_when_rules_have_status() -> None:
    assert (
        _repair_or_reject_llm_source(
            source="status_code",
            op="eq",
            expected=200,
            request={"method": "DELETE", "url": "https://restful-booker.herokuapp.com/booking/1"},
            rule_assertions=[{"source": "status_code", "op": "eq", "expected": 201}],
        )
        == ""
    )


def test_root_json_scalar_eq_is_rewritten_to_request_body_field() -> None:
    assert (
        _repair_or_reject_llm_source(
            source="json",
            op="eq",
            expected="write API test updated",
            request={
                "method": "PUT",
                "url": "https://jsonplaceholder.typicode.com/posts/1",
                "json": {"id": 1, "title": "write API test updated", "body": "updated by automated test", "userId": 1},
            },
            rule_assertions=[],
        )
        == "json.title"
    )


def test_booking_create_body_field_is_rewritten_to_wrapped_response_field() -> None:
    assert (
        _repair_or_reject_llm_source(
            source="json.firstname",
            op="eq",
            expected="Jim",
            request={
                "method": "POST",
                "url": "https://restful-booker.herokuapp.com/booking",
                "json": {"firstname": "Jim", "lastname": "Brown"},
            },
            rule_assertions=[],
        )
        == "json.booking.firstname"
    )


def test_root_json_scalar_contains_is_rejected_as_brittle() -> None:
    assert (
        _repair_or_reject_llm_source(
            source="json",
            op="contains",
            expected="login successful",
            request={"method": "GET", "url": "https://petstore.swagger.io/v2/user/login"},
            rule_assertions=[],
        )
        == ""
    )


def test_missing_expected_type_assertion_is_rejected() -> None:
    assert _missing_required_expected("type_in", None) is True
    assert _missing_required_expected("exists", None) is False


def test_content_type_exact_json_assertion_is_detected() -> None:
    assert _is_json_content_type_exact_assertion("headers.Content-Type", "eq", "application/json") is True
    assert _is_json_content_type_assertion("headers.Content-Type", "application/json") is True
    assert _is_unsafe_llm_header_assertion("headers.api_key", "special-key") is True
    assert _is_unsafe_llm_header_assertion("headers.Content-Type", "application/json") is False


def test_unknown_json_field_is_rejected_when_endpoint_fields_are_known() -> None:
    assert (
        _repair_or_reject_llm_source(
            source="json.token",
            op="exists",
            expected=None,
            request={"method": "GET", "url": "https://restful-booker.herokuapp.com/booking/1"},
            rule_assertions=[],
            known_endpoint_fields=["firstname", "lastname", "totalprice"],
        )
        == ""
    )


def test_root_json_presence_assertion_is_rejected_as_redundant_or_brittle() -> None:
    assert (
        _repair_or_reject_llm_source(
            source="json",
            op="not_exists",
            expected=None,
            request={"method": "DELETE", "url": "https://petstore.swagger.io/v2/pet/1"},
            rule_assertions=[],
        )
        == ""
    )


def test_root_json_exists_field_hint_is_kept_as_field_presence() -> None:
    assert (
        _repair_or_reject_llm_source(
            source="json",
            op="exists",
            expected="message",
            request={"method": "GET", "url": "https://petstore.swagger.io/v2/user/login"},
            rule_assertions=[{"source": "json", "op": "type_in", "expected": ["object", "array"]}],
        )
        == "json.message"
    )


def test_path_identifier_guess_is_rejected_without_response_schema() -> None:
    assert (
        _repair_or_reject_llm_source(
            source="json.petId",
            op="eq",
            expected="{{pet_id}}",
            request={"method": "GET", "url": "https://petstore.swagger.io/v2/pet/{{pet_id}}"},
            rule_assertions=[],
            known_endpoint_fields=[],
        )
        == ""
    )


def test_root_json_object_equality_is_rejected() -> None:
    assert (
        _repair_or_reject_llm_source(
            source="json",
            op="eq",
            expected={},
            request={"method": "DELETE", "url": "https://restful-booker.herokuapp.com/booking/1"},
            rule_assertions=[],
        )
        == ""
    )
