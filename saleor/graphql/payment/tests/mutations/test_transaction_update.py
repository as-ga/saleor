from decimal import Decimal

import graphene
import pytest

from .....order import OrderEvents
from .....order.utils import update_order_authorize_data, update_order_charge_data
from .....payment import TransactionEventStatus
from .....payment.error_codes import TransactionUpdateErrorCode
from .....payment.models import TransactionEvent, TransactionItem
from ....tests.utils import assert_no_permission, get_graphql_content
from ...enums import (
    TransactionActionEnum,
    TransactionEventActionTypeEnum,
    TransactionEventStatusEnum,
)

TEST_SERVER_DOMAIN = "testserver.com"

MUTATION_TRANSACTION_UPDATE = """
mutation TransactionUpdate(
    $id: ID!,
    $transaction_event: TransactionEventInput,
    $transaction: TransactionUpdateInput
    ){
    transactionUpdate(
            id: $id,
            transactionEvent: $transaction_event,
            transaction: $transaction
        ){
        transaction{
                id
                actions
                pspReference
                type
                status
                modifiedAt
                createdAt
                externalUrl
                authorizedAmount{
                    amount
                    currency
                }
                voidedAmount{
                    currency
                    amount
                }
                chargedAmount{
                    currency
                    amount
                }
                refundedAmount{
                    currency
                    amount
                }
                privateMetadata{
                    key
                    value
                }
                metadata{
                    key
                    value
                }
                events{
                    status
                    pspReference
                    name
                    createdAt
                    externalUrl
                    amount{
                        amount
                        currency
                    }
                    type
                }
        }
        errors{
            field
            message
            code
        }
    }
}
"""


def test_only_owner_can_update_its_transaction_by_app(
    transaction_item_created_by_app,
    permission_manage_payments,
    app_api_client,
    external_app,
):
    # given
    transaction = transaction_item_created_by_app
    transaction.app = external_app
    transaction.save()

    status = "Captured for 10$"

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "status": status,
        },
    }
    # when
    response = app_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    assert_no_permission(response)


def test_transaction_update_status_by_app(
    transaction_item_created_by_app, permission_manage_payments, app_api_client
):
    # given
    transaction = transaction_item_created_by_app
    status = "Captured for 10$"

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "status": status,
        },
    }

    # when
    response = app_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    transaction.refresh_from_db()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]
    assert data["status"] == status
    assert transaction_item_created_by_app.status == status


def test_transaction_update_metadata_by_app(
    transaction_item_created_by_app, permission_manage_payments, app_api_client
):
    # given
    transaction = transaction_item_created_by_app

    meta_key = "key-name"
    meta_value = "key_value"
    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "metadata": [{"key": meta_key, "value": meta_value}],
        },
    }

    # when
    response = app_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    transaction.refresh_from_db()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]
    assert len(data["metadata"]) == 1
    assert data["metadata"][0]["key"] == meta_key
    assert data["metadata"][0]["value"] == meta_value
    assert transaction_item_created_by_app.metadata == {meta_key: meta_value}


def test_transaction_update_metadata_incorrect_key_by_app(
    transaction_item_created_by_app, permission_manage_payments, app_api_client
):
    # given
    transaction = transaction_item_created_by_app

    meta_key = ""
    meta_value = "key_value"
    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "metadata": [{"key": meta_key, "value": meta_value}],
        },
    }

    # when
    response = app_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    content = get_graphql_content(response, ignore_errors=True)
    assert not content["data"]["transactionUpdate"]["transaction"]
    errors = content["data"]["transactionUpdate"]["errors"]
    assert len(errors) == 1
    error = errors[0]
    assert error["code"] == TransactionUpdateErrorCode.METADATA_KEY_REQUIRED.name


def test_transaction_update_private_metadata_by_app(
    transaction_item_created_by_app, permission_manage_payments, app_api_client
):
    # given
    transaction = transaction_item_created_by_app

    meta_key = "key-name"
    meta_value = "key_value"
    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "privateMetadata": [{"key": meta_key, "value": meta_value}],
        },
    }

    # when
    response = app_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    transaction.refresh_from_db()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]
    assert len(data["privateMetadata"]) == 1
    assert data["privateMetadata"][0]["key"] == meta_key
    assert data["privateMetadata"][0]["value"] == meta_value
    assert transaction_item_created_by_app.private_metadata == {meta_key: meta_value}


def test_transaction_update_private_metadata_incorrect_key_by_app(
    transaction_item_created_by_app, permission_manage_payments, app_api_client
):
    # given
    transaction = transaction_item_created_by_app

    meta_key = ""
    meta_value = "key_value"
    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "privateMetadata": [{"key": meta_key, "value": meta_value}],
        },
    }

    # when
    response = app_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    content = get_graphql_content(response, ignore_errors=True)
    assert not content["data"]["transactionUpdate"]["transaction"]
    errors = content["data"]["transactionUpdate"]["errors"]
    assert len(errors) == 1
    error = errors[0]
    assert error["code"] == TransactionUpdateErrorCode.METADATA_KEY_REQUIRED.name


def test_transaction_update_external_url_by_app(
    transaction_item_created_by_app, permission_manage_payments, app_api_client
):
    # given
    transaction = transaction_item_created_by_app
    external_url = f"http://{TEST_SERVER_DOMAIN}/external-url"

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "externalUrl": external_url,
        },
    }

    # when
    response = app_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    transaction.refresh_from_db()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]
    assert data["externalUrl"] == external_url
    assert transaction_item_created_by_app.external_url == external_url


def test_transaction_update_external_url_incorrect_url_format_by_app(
    transaction_item_created_by_app, permission_manage_payments, app_api_client
):
    # given
    transaction = transaction_item_created_by_app
    external_url = "incorrect"

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "externalUrl": external_url,
        },
    }

    # when
    response = app_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    content = get_graphql_content(response, ignore_errors=True)
    assert not content["data"]["transactionUpdate"]["transaction"]
    errors = content["data"]["transactionUpdate"]["errors"]
    assert len(errors) == 1
    error = errors[0]
    assert error["code"] == TransactionUpdateErrorCode.INVALID.name


def test_transaction_update_type_by_app(
    transaction_item_created_by_app, permission_manage_payments, app_api_client
):
    # given
    transaction = transaction_item_created_by_app
    type = "New credit card"

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "type": type,
        },
    }

    # when
    response = app_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    transaction.refresh_from_db()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]
    assert data["type"] == type
    assert transaction.type == type


def test_transaction_update_psp_reference_by_app(
    transaction_item_created_by_app, permission_manage_payments, app_api_client
):
    # given
    psp_peference = "PSP:123AAA"
    transaction = transaction_item_created_by_app

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "pspReference": psp_peference,
        },
    }

    # when
    response = app_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    transaction.refresh_from_db()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]
    assert data["pspReference"] == psp_peference
    assert transaction.psp_reference == psp_peference


def test_transaction_update_available_actions_by_app(
    transaction_item_created_by_app, permission_manage_payments, app_api_client
):
    # given
    transaction = transaction_item_created_by_app
    available_actions = [TransactionActionEnum.REFUND.name]

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "availableActions": available_actions,
        },
    }

    # when
    response = app_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    transaction.refresh_from_db()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]
    assert data["actions"] == available_actions
    assert transaction.available_actions == ["refund"]


@pytest.mark.parametrize(
    "field_name, response_field, db_field_name, value",
    [
        ("amountAuthorized", "authorizedAmount", "authorized_value", Decimal("12")),
        ("amountCharged", "chargedAmount", "charged_value", Decimal("13")),
        ("amountVoided", "voidedAmount", "voided_value", Decimal("14")),
        ("amountRefunded", "refundedAmount", "refunded_value", Decimal("15")),
    ],
)
def test_transaction_update_amounts_by_app(
    field_name,
    response_field,
    db_field_name,
    value,
    transaction_item_created_by_app,
    permission_manage_payments,
    app_api_client,
):
    # given
    transaction = transaction_item_created_by_app
    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {field_name: {"amount": value, "currency": "USD"}},
    }

    # when
    response = app_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    transaction.refresh_from_db()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]
    assert data[response_field]["amount"] == value
    assert getattr(transaction_item_created_by_app, db_field_name) == value


def test_transaction_update_for_order_increases_order_total_authorized_by_app(
    order_with_lines,
    permission_manage_payments,
    app_api_client,
    transaction_item_created_by_app,
):
    # given
    transaction = transaction_item_created_by_app
    previously_authorized_value = Decimal("90")
    old_transaction = order_with_lines.payment_transactions.create(
        authorized_value=previously_authorized_value, currency=order_with_lines.currency
    )
    update_order_authorize_data(
        order_with_lines,
    )
    assert (
        order_with_lines.total_authorized_amount
        == previously_authorized_value + transaction.authorized_value
    )

    authorized_value = transaction.authorized_value + Decimal("10")

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "amountAuthorized": {
                "amount": authorized_value,
                "currency": "USD",
            },
        },
    }

    # when
    response = app_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    order_with_lines.refresh_from_db()
    transaction = order_with_lines.payment_transactions.exclude(
        id=old_transaction.id
    ).last()
    content = get_graphql_content(response)

    data = content["data"]["transactionUpdate"]["transaction"]
    assert data["authorizedAmount"]["amount"] == authorized_value
    assert (
        order_with_lines.total_authorized_amount
        == previously_authorized_value + authorized_value
    )
    assert authorized_value == transaction.authorized_value


def test_transaction_update_for_order_reduces_order_total_authorized_by_app(
    order_with_lines,
    permission_manage_payments,
    app_api_client,
    transaction_item_created_by_app,
):
    # given
    transaction = transaction_item_created_by_app
    transaction.authorized_value = Decimal("10")
    transaction.save()
    previously_authorized_value = Decimal("90")
    old_transaction = order_with_lines.payment_transactions.create(
        authorized_value=previously_authorized_value, currency=order_with_lines.currency
    )
    update_order_authorize_data(order_with_lines)
    assert (
        order_with_lines.total_authorized_amount
        == previously_authorized_value + transaction.authorized_value
    )

    authorized_value = transaction.authorized_value - Decimal("5")

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "amountAuthorized": {
                "amount": authorized_value,
                "currency": "USD",
            },
        },
    }

    # when
    response = app_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    order_with_lines.refresh_from_db()
    transaction = order_with_lines.payment_transactions.exclude(
        id=old_transaction.id
    ).last()
    content = get_graphql_content(response)

    data = content["data"]["transactionUpdate"]["transaction"]
    assert data["authorizedAmount"]["amount"] == authorized_value
    assert (
        order_with_lines.total_authorized_amount
        == previously_authorized_value + authorized_value
    )
    assert authorized_value == transaction.authorized_value


def test_transaction_update_for_order_reduces_transaction_authorized_to_zero_by_app(
    order_with_lines,
    permission_manage_payments,
    app_api_client,
    transaction_item_created_by_app,
):
    # given
    transaction = transaction_item_created_by_app
    previously_authorized_value = Decimal("90")
    old_transaction = order_with_lines.payment_transactions.create(
        authorized_value=previously_authorized_value, currency=order_with_lines.currency
    )
    update_order_authorize_data(order_with_lines)
    assert (
        order_with_lines.total_authorized_amount
        == previously_authorized_value + transaction.authorized_value
    )

    authorized_value = Decimal("0")

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "amountAuthorized": {
                "amount": authorized_value,
                "currency": "USD",
            },
        },
    }

    # when
    response = app_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    order_with_lines.refresh_from_db()
    transaction = order_with_lines.payment_transactions.exclude(
        id=old_transaction.id
    ).last()
    content = get_graphql_content(response)

    data = content["data"]["transactionUpdate"]["transaction"]
    assert data["authorizedAmount"]["amount"] == authorized_value
    assert order_with_lines.total_authorized_amount == previously_authorized_value
    assert authorized_value == transaction.authorized_value


def test_transaction_update_for_order_increases_order_total_charged_by_app(
    order_with_lines,
    permission_manage_payments,
    app_api_client,
    transaction_item_created_by_app,
):
    # given
    transaction = transaction_item_created_by_app
    previously_charged_value = Decimal("90")
    old_transaction = order_with_lines.payment_transactions.create(
        charged_value=previously_charged_value, currency=order_with_lines.currency
    )

    update_order_charge_data(order_with_lines)
    assert (
        order_with_lines.total_charged_amount
        == previously_charged_value + transaction.charged_value
    )

    charged_value = transaction.charged_value + Decimal("10")

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "amountCharged": {
                "amount": charged_value,
                "currency": "USD",
            },
        },
    }

    # when
    response = app_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    order_with_lines.refresh_from_db()
    transaction = order_with_lines.payment_transactions.exclude(
        id=old_transaction.id
    ).last()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]
    assert data["chargedAmount"]["amount"] == charged_value
    assert (
        order_with_lines.total_charged_amount
        == previously_charged_value + charged_value
    )
    assert charged_value == transaction.charged_value


def test_transaction_update_for_order_reduces_order_total_charged_by_app(
    order_with_lines,
    permission_manage_payments,
    app_api_client,
    transaction_item_created_by_app,
):
    # given
    transaction = transaction_item_created_by_app
    previously_charged_value = Decimal("90")
    old_transaction = order_with_lines.payment_transactions.create(
        charged_value=previously_charged_value, currency=order_with_lines.currency
    )
    transaction.charged_value = Decimal("30")
    transaction.save()

    update_order_charge_data(order_with_lines)
    assert (
        order_with_lines.total_charged_amount
        == previously_charged_value + transaction.charged_value
    )

    charged_value = transaction.charged_value - Decimal("5")

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "amountCharged": {
                "amount": charged_value,
                "currency": "USD",
            },
        },
    }

    # when
    response = app_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    order_with_lines.refresh_from_db()
    transaction = order_with_lines.payment_transactions.exclude(
        id=old_transaction.id
    ).last()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]
    assert data["chargedAmount"]["amount"] == charged_value
    assert (
        order_with_lines.total_charged_amount
        == previously_charged_value + charged_value
    )
    assert charged_value == transaction.charged_value


def test_transaction_update_for_order_reduces_transaction_charged_to_zero_by_app(
    order_with_lines,
    permission_manage_payments,
    app_api_client,
    transaction_item_created_by_app,
):
    # given
    transaction = transaction_item_created_by_app
    previously_charged_value = Decimal("90")
    old_transaction = order_with_lines.payment_transactions.create(
        charged_value=previously_charged_value, currency=order_with_lines.currency
    )
    transaction.charged_value = Decimal("30")
    transaction.save()

    update_order_charge_data(order_with_lines)
    assert (
        order_with_lines.total_charged_amount
        == previously_charged_value + transaction.charged_value
    )

    charged_value = Decimal("0")

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "amountCharged": {
                "amount": charged_value,
                "currency": "USD",
            },
        },
    }

    # when
    response = app_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    order_with_lines.refresh_from_db()
    transaction = order_with_lines.payment_transactions.exclude(
        id=old_transaction.id
    ).last()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]
    assert data["chargedAmount"]["amount"] == charged_value
    assert order_with_lines.total_charged_amount == previously_charged_value
    assert charged_value == transaction.charged_value


def test_transaction_update_multiple_amounts_provided_by_app(
    transaction_item_created_by_app, permission_manage_payments, app_api_client
):
    # given
    transaction = transaction_item_created_by_app
    authorized_value = Decimal("10")
    charged_value = Decimal("11")
    refunded_value = Decimal("12")
    voided_value = Decimal("13")

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "amountAuthorized": {
                "amount": authorized_value,
                "currency": "USD",
            },
            "amountCharged": {
                "amount": charged_value,
                "currency": "USD",
            },
            "amountRefunded": {
                "amount": refunded_value,
                "currency": "USD",
            },
            "amountVoided": {
                "amount": voided_value,
                "currency": "USD",
            },
        },
    }

    # when
    response = app_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    transaction = TransactionItem.objects.first()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]
    assert data["authorizedAmount"]["amount"] == authorized_value
    assert data["chargedAmount"]["amount"] == charged_value
    assert data["refundedAmount"]["amount"] == refunded_value
    assert data["voidedAmount"]["amount"] == voided_value

    assert transaction.authorized_value == authorized_value
    assert transaction.charged_value == charged_value
    assert transaction.voided_value == voided_value
    assert transaction.refunded_value == refunded_value


def test_transaction_update_for_order_missing_permission_by_app(
    transaction_item_created_by_app, app_api_client
):
    # given
    transaction = transaction_item_created_by_app
    status = "Authorized for 10$"
    type = "Credit Card"

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "status": status,
            "type": type,
        },
    }

    # when
    response = app_api_client.post_graphql(MUTATION_TRANSACTION_UPDATE, variables)

    # then
    assert_no_permission(response)


@pytest.mark.parametrize(
    "amount_field_name, amount_db_field",
    [
        ("amountAuthorized", "authorized_value"),
        ("amountCharged", "charged_value"),
        ("amountVoided", "voided_value"),
        ("amountRefunded", "refunded_value"),
    ],
)
def test_transaction_update_incorrect_currency_by_app(
    amount_field_name,
    amount_db_field,
    transaction_item_created_by_app,
    permission_manage_payments,
    app_api_client,
):
    # given
    transaction = transaction_item_created_by_app
    expected_value = Decimal("10")

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            amount_field_name: {
                "amount": expected_value,
                "currency": "PLN",
            },
        },
    }

    # when
    response = app_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]
    assert data["errors"][0]["field"] == amount_field_name
    assert (
        data["errors"][0]["code"] == TransactionUpdateErrorCode.INCORRECT_CURRENCY.name
    )


def test_transaction_update_adds_transaction_event_to_order_by_app(
    transaction_item_created_by_app,
    order_with_lines,
    permission_manage_payments,
    app_api_client,
):
    # given
    transaction = transaction_item_created_by_app
    transaction_status = "PENDING"
    transaction_reference = "transaction reference"
    transaction_name = "Processing transaction"

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction_event": {
            "status": transaction_status,
            "pspReference": transaction_reference,
            "name": transaction_name,
        },
    }

    # when
    response = app_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )
    # then
    event = order_with_lines.events.first()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]

    assert not data["errors"]
    assert event.type == OrderEvents.TRANSACTION_EVENT
    assert event.parameters == {
        "message": transaction_name,
        "reference": transaction_reference,
        "status": transaction_status.lower(),
    }


def test_creates_transaction_event_for_order_by_app(
    transaction_item_created_by_app,
    order_with_lines,
    permission_manage_payments,
    app_api_client,
):
    # given

    transaction = order_with_lines.payment_transactions.first()
    event_status = TransactionEventStatus.FAILURE
    event_reference = "PSP-ref"
    event_name = "Failed authorization"
    external_url = f"http://{TEST_SERVER_DOMAIN}/external-url"
    amount_value = Decimal("10")
    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction_event": {
            "status": TransactionEventStatusEnum.FAILURE.name,
            "pspReference": event_reference,
            "name": event_name,
            "externalUrl": external_url,
            "amount": amount_value,
            "type": TransactionEventActionTypeEnum.AUTHORIZE.name,
        },
    }

    # when
    response = app_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]

    events_data = data["events"]
    assert len(events_data) == 1
    event_data = events_data[0]
    assert event_data["name"] == event_name
    assert event_data["status"] == TransactionEventStatusEnum.FAILURE.name
    assert event_data["pspReference"] == event_reference
    assert event_data["externalUrl"] == external_url
    assert event_data["amount"]["currency"] == transaction.currency
    assert event_data["amount"]["amount"] == amount_value
    assert event_data["type"] == TransactionEventActionTypeEnum.AUTHORIZE.name

    assert transaction.events.count() == 1
    event = transaction.events.first()
    assert event.name == event_name
    assert event.status == event_status
    assert event.psp_reference == event_reference
    assert event.external_url == external_url
    assert event.amount_value == amount_value
    assert event.currency == transaction.currency
    assert event.type == TransactionEventActionTypeEnum.AUTHORIZE.value


def test_only_owner_can_update_its_transaction_by_staff(
    transaction_item_created_by_app,
    permission_manage_payments,
    staff_api_client,
):
    # given
    transaction = transaction_item_created_by_app

    status = "Captured for 10$"

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "status": status,
        },
    }
    # when
    response = staff_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    assert_no_permission(response)


def test_transaction_update_status_by_staff(
    transaction_item_created_by_user, permission_manage_payments, staff_api_client
):
    # given
    transaction = transaction_item_created_by_user
    status = "Captured for 10$"

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "status": status,
        },
    }

    # when
    response = staff_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    transaction.refresh_from_db()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]
    assert data["status"] == status
    assert transaction_item_created_by_user.status == status


def test_transaction_update_external_url_by_staff(
    transaction_item_created_by_user, permission_manage_payments, staff_api_client
):
    # given
    transaction = transaction_item_created_by_user
    external_url = f"http://{TEST_SERVER_DOMAIN}/external-url"

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "externalUrl": external_url,
        },
    }

    # when
    response = staff_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    transaction.refresh_from_db()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]
    assert data["externalUrl"] == external_url
    assert transaction_item_created_by_user.external_url == external_url


def test_transaction_update_external_url_incorrect_url_format_by_staff(
    transaction_item_created_by_user, permission_manage_payments, staff_api_client
):
    # given
    transaction = transaction_item_created_by_user
    external_url = "incorrect"

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "externalUrl": external_url,
        },
    }

    # when
    response = staff_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    content = get_graphql_content(response, ignore_errors=True)
    assert not content["data"]["transactionUpdate"]["transaction"]
    errors = content["data"]["transactionUpdate"]["errors"]
    assert len(errors) == 1
    error = errors[0]
    assert error["code"] == TransactionUpdateErrorCode.INVALID.name


def test_transaction_update_metadata_by_staff(
    transaction_item_created_by_user, permission_manage_payments, staff_api_client
):
    # given
    transaction = transaction_item_created_by_user

    meta_key = "key-name"
    meta_value = "key_value"
    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "metadata": [{"key": meta_key, "value": meta_value}],
        },
    }

    # when
    response = staff_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    transaction.refresh_from_db()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]
    assert len(data["metadata"]) == 1
    assert data["metadata"][0]["key"] == meta_key
    assert data["metadata"][0]["value"] == meta_value
    assert transaction.metadata == {meta_key: meta_value}


def test_transaction_update_metadata_incorrect_key_by_staff(
    transaction_item_created_by_user, permission_manage_payments, staff_api_client
):
    # given
    transaction = transaction_item_created_by_user

    meta_key = ""
    meta_value = "key_value"
    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "metadata": [{"key": meta_key, "value": meta_value}],
        },
    }

    # when
    response = staff_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    content = get_graphql_content(response, ignore_errors=True)
    assert not content["data"]["transactionUpdate"]["transaction"]
    errors = content["data"]["transactionUpdate"]["errors"]
    assert len(errors) == 1
    error = errors[0]
    assert error["code"] == TransactionUpdateErrorCode.METADATA_KEY_REQUIRED.name


def test_transaction_update_private_metadata_by_staff(
    transaction_item_created_by_user, permission_manage_payments, staff_api_client
):
    # given
    transaction = transaction_item_created_by_user

    meta_key = "key-name"
    meta_value = "key_value"
    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "privateMetadata": [{"key": meta_key, "value": meta_value}],
        },
    }

    # when
    response = staff_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    transaction.refresh_from_db()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]
    assert len(data["privateMetadata"]) == 1
    assert data["privateMetadata"][0]["key"] == meta_key
    assert data["privateMetadata"][0]["value"] == meta_value
    assert transaction.private_metadata == {meta_key: meta_value}


def test_transaction_update_private_metadata_incorrect_key_by_staff(
    transaction_item_created_by_user, permission_manage_payments, staff_api_client
):
    # given
    transaction = transaction_item_created_by_user

    meta_key = ""
    meta_value = "key_value"
    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "privateMetadata": [{"key": meta_key, "value": meta_value}],
        },
    }

    # when
    response = staff_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    content = get_graphql_content(response, ignore_errors=True)
    assert not content["data"]["transactionUpdate"]["transaction"]
    errors = content["data"]["transactionUpdate"]["errors"]
    assert len(errors) == 1
    error = errors[0]
    assert error["code"] == TransactionUpdateErrorCode.METADATA_KEY_REQUIRED.name


def test_transaction_update_type_by_staff(
    transaction_item_created_by_user, permission_manage_payments, staff_api_client
):
    # given
    transaction = transaction_item_created_by_user
    type = "New credit card"

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "type": type,
        },
    }

    # when
    response = staff_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    transaction.refresh_from_db()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]
    assert data["type"] == type
    assert transaction.type == type


def test_transaction_update_psp_reference_by_staff(
    transaction_item_created_by_user, permission_manage_payments, staff_api_client
):
    # given
    reference = "PSP:123AAA"
    transaction = transaction_item_created_by_user

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "pspReference": reference,
        },
    }

    # when
    response = staff_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    transaction.refresh_from_db()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]
    assert data["pspReference"] == reference
    assert transaction.psp_reference == reference


def test_transaction_update_available_actions_by_staff(
    transaction_item_created_by_user, permission_manage_payments, staff_api_client
):
    # given
    transaction = transaction_item_created_by_user
    available_actions = [TransactionActionEnum.REFUND.name]

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "availableActions": available_actions,
        },
    }

    # when
    response = staff_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    transaction.refresh_from_db()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]
    assert data["actions"] == available_actions
    assert transaction.available_actions == ["refund"]


@pytest.mark.parametrize(
    "field_name, response_field, db_field_name, value",
    [
        ("amountAuthorized", "authorizedAmount", "authorized_value", Decimal("12")),
        ("amountCharged", "chargedAmount", "charged_value", Decimal("13")),
        ("amountVoided", "voidedAmount", "voided_value", Decimal("14")),
        ("amountRefunded", "refundedAmount", "refunded_value", Decimal("15")),
    ],
)
def test_transaction_update_amounts_by_staff(
    field_name,
    response_field,
    db_field_name,
    value,
    transaction_item_created_by_user,
    permission_manage_payments,
    staff_api_client,
):
    # given
    transaction = transaction_item_created_by_user
    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {field_name: {"amount": value, "currency": "USD"}},
    }

    # when
    response = staff_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    transaction.refresh_from_db()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]
    assert data[response_field]["amount"] == value
    assert getattr(transaction_item_created_by_user, db_field_name) == value


def test_transaction_update_for_order_increases_order_total_authorized_by_staff(
    order_with_lines,
    permission_manage_payments,
    staff_api_client,
    transaction_item_created_by_user,
):
    # given
    transaction = transaction_item_created_by_user
    previously_authorized_value = Decimal("90")
    old_transaction = order_with_lines.payment_transactions.create(
        authorized_value=previously_authorized_value, currency=order_with_lines.currency
    )
    update_order_authorize_data(
        order_with_lines,
    )
    assert (
        order_with_lines.total_authorized_amount
        == previously_authorized_value + transaction.authorized_value
    )

    authorized_value = transaction.authorized_value + Decimal("10")

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "amountAuthorized": {
                "amount": authorized_value,
                "currency": "USD",
            },
        },
    }

    # when
    response = staff_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    order_with_lines.refresh_from_db()
    transaction = order_with_lines.payment_transactions.exclude(
        id=old_transaction.id
    ).last()
    content = get_graphql_content(response)

    data = content["data"]["transactionUpdate"]["transaction"]
    assert data["authorizedAmount"]["amount"] == authorized_value
    assert (
        order_with_lines.total_authorized_amount
        == previously_authorized_value + authorized_value
    )
    assert authorized_value == transaction.authorized_value


def test_transaction_update_for_order_reduces_order_total_authorized_by_staff(
    order_with_lines,
    permission_manage_payments,
    staff_api_client,
    transaction_item_created_by_user,
):
    # given
    transaction = transaction_item_created_by_user
    transaction.authorized_value = Decimal("10")
    transaction.save()
    previously_authorized_value = Decimal("90")
    old_transaction = order_with_lines.payment_transactions.create(
        authorized_value=previously_authorized_value, currency=order_with_lines.currency
    )
    update_order_authorize_data(order_with_lines)
    assert (
        order_with_lines.total_authorized_amount
        == previously_authorized_value + transaction.authorized_value
    )

    authorized_value = transaction.authorized_value - Decimal("5")

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "amountAuthorized": {
                "amount": authorized_value,
                "currency": "USD",
            },
        },
    }

    # when
    response = staff_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    order_with_lines.refresh_from_db()
    transaction = order_with_lines.payment_transactions.exclude(
        id=old_transaction.id
    ).last()
    content = get_graphql_content(response)

    data = content["data"]["transactionUpdate"]["transaction"]
    assert data["authorizedAmount"]["amount"] == authorized_value
    assert (
        order_with_lines.total_authorized_amount
        == previously_authorized_value + authorized_value
    )
    assert authorized_value == transaction.authorized_value


def test_transaction_update_for_order_reduces_transaction_authorized_to_zero_by_staff(
    order_with_lines,
    permission_manage_payments,
    staff_api_client,
    transaction_item_created_by_user,
):
    # given
    transaction = transaction_item_created_by_user
    previously_authorized_value = Decimal("90")
    old_transaction = order_with_lines.payment_transactions.create(
        authorized_value=previously_authorized_value, currency=order_with_lines.currency
    )
    update_order_authorize_data(order_with_lines)
    assert (
        order_with_lines.total_authorized_amount
        == previously_authorized_value + transaction.authorized_value
    )

    authorized_value = Decimal("0")

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "amountAuthorized": {
                "amount": authorized_value,
                "currency": "USD",
            },
        },
    }

    # when
    response = staff_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    order_with_lines.refresh_from_db()
    transaction = order_with_lines.payment_transactions.exclude(
        id=old_transaction.id
    ).last()
    content = get_graphql_content(response)

    data = content["data"]["transactionUpdate"]["transaction"]
    assert data["authorizedAmount"]["amount"] == authorized_value
    assert order_with_lines.total_authorized_amount == previously_authorized_value
    assert authorized_value == transaction.authorized_value


def test_transaction_update_for_order_increases_order_total_charged_by_staff(
    order_with_lines,
    permission_manage_payments,
    staff_api_client,
    transaction_item_created_by_user,
):
    # given
    transaction = transaction_item_created_by_user
    previously_charged_value = Decimal("90")
    old_transaction = order_with_lines.payment_transactions.create(
        charged_value=previously_charged_value, currency=order_with_lines.currency
    )

    update_order_charge_data(order_with_lines)
    assert (
        order_with_lines.total_charged_amount
        == previously_charged_value + transaction.charged_value
    )

    charged_value = transaction.charged_value + Decimal("10")

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "amountCharged": {
                "amount": charged_value,
                "currency": "USD",
            },
        },
    }

    # when
    response = staff_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    order_with_lines.refresh_from_db()
    transaction = order_with_lines.payment_transactions.exclude(
        id=old_transaction.id
    ).last()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]
    assert data["chargedAmount"]["amount"] == charged_value
    assert (
        order_with_lines.total_charged_amount
        == previously_charged_value + charged_value
    )
    assert charged_value == transaction.charged_value


def test_transaction_update_for_order_reduces_order_total_charged_by_staff(
    order_with_lines,
    permission_manage_payments,
    staff_api_client,
    transaction_item_created_by_user,
):
    # given
    transaction = transaction_item_created_by_user
    previously_charged_value = Decimal("90")
    old_transaction = order_with_lines.payment_transactions.create(
        charged_value=previously_charged_value, currency=order_with_lines.currency
    )
    transaction.charged_value = Decimal("30")
    transaction.save()

    update_order_charge_data(order_with_lines)
    assert (
        order_with_lines.total_charged_amount
        == previously_charged_value + transaction.charged_value
    )

    charged_value = transaction.charged_value - Decimal("5")

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "amountCharged": {
                "amount": charged_value,
                "currency": "USD",
            },
        },
    }

    # when
    response = staff_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    order_with_lines.refresh_from_db()
    transaction = order_with_lines.payment_transactions.exclude(
        id=old_transaction.id
    ).last()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]
    assert data["chargedAmount"]["amount"] == charged_value
    assert (
        order_with_lines.total_charged_amount
        == previously_charged_value + charged_value
    )
    assert charged_value == transaction.charged_value


def test_transaction_update_for_order_reduces_transaction_charged_to_zero_by_staff(
    order_with_lines,
    permission_manage_payments,
    staff_api_client,
    transaction_item_created_by_user,
):
    # given
    transaction = transaction_item_created_by_user
    previously_charged_value = Decimal("90")
    old_transaction = order_with_lines.payment_transactions.create(
        charged_value=previously_charged_value, currency=order_with_lines.currency
    )
    transaction.charged_value = Decimal("30")
    transaction.save()

    update_order_charge_data(order_with_lines)
    assert (
        order_with_lines.total_charged_amount
        == previously_charged_value + transaction.charged_value
    )

    charged_value = Decimal("0")

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "amountCharged": {
                "amount": charged_value,
                "currency": "USD",
            },
        },
    }

    # when
    response = staff_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    order_with_lines.refresh_from_db()
    transaction = order_with_lines.payment_transactions.exclude(
        id=old_transaction.id
    ).last()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]
    assert data["chargedAmount"]["amount"] == charged_value
    assert order_with_lines.total_charged_amount == previously_charged_value
    assert charged_value == transaction.charged_value


def test_transaction_update_multiple_amounts_provided_by_staff(
    transaction_item_created_by_user, permission_manage_payments, staff_api_client
):
    # given
    transaction = transaction_item_created_by_user
    authorized_value = Decimal("10")
    charged_value = Decimal("11")
    refunded_value = Decimal("12")
    voided_value = Decimal("13")

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "amountAuthorized": {
                "amount": authorized_value,
                "currency": "USD",
            },
            "amountCharged": {
                "amount": charged_value,
                "currency": "USD",
            },
            "amountRefunded": {
                "amount": refunded_value,
                "currency": "USD",
            },
            "amountVoided": {
                "amount": voided_value,
                "currency": "USD",
            },
        },
    }

    # when
    response = staff_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    transaction = TransactionItem.objects.first()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]
    assert data["authorizedAmount"]["amount"] == authorized_value
    assert data["chargedAmount"]["amount"] == charged_value
    assert data["refundedAmount"]["amount"] == refunded_value
    assert data["voidedAmount"]["amount"] == voided_value

    assert transaction.authorized_value == authorized_value
    assert transaction.charged_value == charged_value
    assert transaction.voided_value == voided_value
    assert transaction.refunded_value == refunded_value


def test_transaction_update_for_order_missing_permission_by_staff(
    transaction_item_created_by_user, staff_api_client
):
    # given
    transaction = transaction_item_created_by_user
    status = "Authorized for 10$"
    type = "Credit Card"

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "status": status,
            "type": type,
        },
    }

    # when
    response = staff_api_client.post_graphql(MUTATION_TRANSACTION_UPDATE, variables)

    # then
    assert_no_permission(response)


@pytest.mark.parametrize(
    "amount_field_name, amount_db_field",
    [
        ("amountAuthorized", "authorized_value"),
        ("amountCharged", "charged_value"),
        ("amountVoided", "voided_value"),
        ("amountRefunded", "refunded_value"),
    ],
)
def test_transaction_update_incorrect_currency_by_staff(
    amount_field_name,
    amount_db_field,
    transaction_item_created_by_user,
    permission_manage_payments,
    staff_api_client,
):
    # given
    transaction = transaction_item_created_by_user
    expected_value = Decimal("10")

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            amount_field_name: {
                "amount": expected_value,
                "currency": "PLN",
            },
        },
    }

    # when
    response = staff_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]
    assert data["errors"][0]["field"] == amount_field_name
    assert (
        data["errors"][0]["code"] == TransactionUpdateErrorCode.INCORRECT_CURRENCY.name
    )


def test_transaction_update_adds_transaction_event_to_order_by_staff(
    transaction_item_created_by_user,
    order_with_lines,
    permission_manage_payments,
    staff_api_client,
):
    # given
    transaction = transaction_item_created_by_user
    transaction_status = "PENDING"
    transaction_reference = "transaction reference"
    transaction_name = "Processing transaction"

    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction_event": {
            "status": transaction_status,
            "pspReference": transaction_reference,
            "name": transaction_name,
        },
    }

    # when
    response = staff_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )
    # then
    event = order_with_lines.events.first()
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]

    assert not data["errors"]
    assert event.type == OrderEvents.TRANSACTION_EVENT
    assert event.parameters == {
        "message": transaction_name,
        "reference": transaction_reference,
        "status": transaction_status.lower(),
    }


def test_creates_transaction_event_for_order_by_staff(
    transaction_item_created_by_user,
    order_with_lines,
    permission_manage_payments,
    staff_api_client,
):
    # given

    transaction = order_with_lines.payment_transactions.first()
    event_status = TransactionEventStatus.FAILURE
    event_reference = "PSP-ref"
    event_name = "Failed authorization"
    external_url = f"http://{TEST_SERVER_DOMAIN}/external-url"
    amount_value = Decimal("10")
    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction_event": {
            "status": TransactionEventStatusEnum.FAILURE.name,
            "pspReference": event_reference,
            "name": event_name,
            "externalUrl": external_url,
            "amount": amount_value,
            "type": TransactionEventActionTypeEnum.AUTHORIZE.name,
        },
    }

    # when
    response = staff_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["transactionUpdate"]["transaction"]

    events_data = data["events"]
    assert len(events_data) == 1
    event_data = events_data[0]
    assert event_data["name"] == event_name
    assert event_data["status"] == TransactionEventStatusEnum.FAILURE.name
    assert event_data["pspReference"] == event_reference
    assert event_data["externalUrl"] == external_url
    assert event_data["amount"]["currency"] == transaction.currency
    assert event_data["amount"]["amount"] == amount_value
    assert event_data["type"] == TransactionEventActionTypeEnum.AUTHORIZE.name

    assert transaction.events.count() == 1
    event = transaction.events.first()
    assert event.name == event_name
    assert event.status == event_status
    assert event.psp_reference == event_reference
    assert event.external_url == external_url
    assert event.amount_value == amount_value
    assert event.currency == transaction.currency
    assert event.type == TransactionEventActionTypeEnum.AUTHORIZE.value


def test_transaction_raises_error_when_psp_reference_already_exists_by_staff(
    transaction_item_created_by_user,
    transaction_item_created_by_app,
    order_with_lines,
    permission_manage_payments,
    staff_api_client,
):
    # given

    transaction = transaction_item_created_by_user
    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "pspReference": transaction_item_created_by_app.psp_reference,
        },
    }

    # when
    response = staff_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    content = get_graphql_content(response, ignore_errors=True)
    transaction = content["data"]["transactionUpdate"]["transaction"]
    errors = content["data"]["transactionUpdate"]["errors"]

    assert not transaction
    assert len(errors) == 1
    error = errors[0]
    assert error["code"] == TransactionUpdateErrorCode.UNIQUE.name
    assert error["field"] == "transaction"

    assert order_with_lines.payment_transactions.count() == 2
    assert TransactionEvent.objects.count() == 0


def test_transaction_raises_error_when_psp_reference_already_exists_by_app(
    transaction_item_created_by_user,
    transaction_item_created_by_app,
    order_with_lines,
    permission_manage_payments,
    app_api_client,
):
    # given

    transaction = transaction_item_created_by_app
    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction": {
            "pspReference": transaction_item_created_by_user.psp_reference,
        },
    }

    # when
    response = app_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    content = get_graphql_content(response, ignore_errors=True)
    transaction = content["data"]["transactionUpdate"]["transaction"]
    errors = content["data"]["transactionUpdate"]["errors"]

    assert not transaction
    assert len(errors) == 1
    error = errors[0]
    assert error["code"] == TransactionUpdateErrorCode.UNIQUE.name
    assert error["field"] == "transaction"

    assert order_with_lines.payment_transactions.count() == 2
    assert TransactionEvent.objects.count() == 0


def test_transaction_raises_error_when_event_psp_reference_already_exists_by_staff(
    transaction_item_created_by_user,
    order_with_lines,
    permission_manage_payments,
    staff_api_client,
):
    # given

    event_psp_reference = "event-psp-reference"
    transaction = transaction_item_created_by_user
    transaction_item_created_by_user.events.create(psp_reference=event_psp_reference)
    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction_event": {
            "status": TransactionEventStatusEnum.FAILURE.name,
            "pspReference": event_psp_reference,
            "name": "Event name",
        },
    }

    # when
    response = staff_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    content = get_graphql_content(response, ignore_errors=True)
    transaction = content["data"]["transactionUpdate"]["transaction"]
    errors = content["data"]["transactionUpdate"]["errors"]

    assert not transaction
    assert len(errors) == 1
    error = errors[0]
    assert error["code"] == TransactionUpdateErrorCode.UNIQUE.name
    assert error["field"] == "transactionEvent"

    assert order_with_lines.payment_transactions.count() == 1
    assert TransactionEvent.objects.count() == 1


def test_transaction_raises_error_when_event_psp_reference_already_exists_by_app(
    transaction_item_created_by_app,
    order_with_lines,
    permission_manage_payments,
    app_api_client,
):
    # given

    event_psp_reference = "event-psp-reference"
    transaction = transaction_item_created_by_app
    transaction_item_created_by_app.events.create(psp_reference=event_psp_reference)
    variables = {
        "id": graphene.Node.to_global_id("TransactionItem", transaction.pk),
        "transaction_event": {
            "status": TransactionEventStatusEnum.FAILURE.name,
            "pspReference": event_psp_reference,
            "name": "Event name",
        },
    }

    # when
    response = app_api_client.post_graphql(
        MUTATION_TRANSACTION_UPDATE, variables, permissions=[permission_manage_payments]
    )

    # then
    content = get_graphql_content(response, ignore_errors=True)
    transaction = content["data"]["transactionUpdate"]["transaction"]
    errors = content["data"]["transactionUpdate"]["errors"]

    assert not transaction
    assert len(errors) == 1
    error = errors[0]
    assert error["code"] == TransactionUpdateErrorCode.UNIQUE.name
    assert error["field"] == "transactionEvent"

    assert order_with_lines.payment_transactions.count() == 1
    assert TransactionEvent.objects.count() == 1