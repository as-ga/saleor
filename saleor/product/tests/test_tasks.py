import logging
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import graphene
from django.utils import timezone

from ...discount import RewardValueType
from ...discount.models import Promotion
from ..tasks import (
    _get_preorder_variants_to_clean,
    update_product_discounted_price_task,
    update_products_discounted_prices_for_promotion_task,
    update_products_discounted_prices_of_promotion_task,
    update_products_discounted_prices_of_sale_task,
    update_products_search_vector_task,
    update_variants_names,
)


@patch("saleor.product.utils.variant_prices." "update_products_discounted_prices")
def test_update_products_discounted_prices_of_sale_task(
    update_products_discounted_prices_mock,
    new_sale,
    product_list,
    product,
    category,
    collection,
):
    # given
    new_sale.products.add(product)
    category.products.add(product_list[0])
    new_sale.categories.add(category)
    collection.products.add(product_list[1])
    new_sale.variants.add(product_list[2].variants.first())

    # when
    update_products_discounted_prices_of_sale_task(new_sale.id)

    # then
    update_products_discounted_prices_mock.assert_called_once()
    args, kwargs = update_products_discounted_prices_mock.call_args

    expected_products = [product] + product_list
    assert len(args[0]) == len(expected_products)
    assert {product.id for product in args[0]} == {
        instance.id for instance in expected_products
    }


@patch("saleor.product.tasks.update_products_discounted_prices_of_sale")
def test_update_products_discounted_prices_of_sale_task_discount_does_not_exist(
    update_product_prices_mock, caplog
):
    # given
    caplog.set_level(logging.WARNING)
    discount_id = -1

    # when
    update_products_discounted_prices_of_sale_task(discount_id)

    # then
    update_product_prices_mock.assert_not_called()
    assert f"Cannot find discount with id: {discount_id}" in caplog.text


@patch(
    "saleor.product.tasks.update_products_discounted_prices_for_promotion_task.delay"
)
def test_update_products_discounted_prices_of_promotion_task(
    update_products_discounted_prices_mock,
    product,
):
    # given
    promotion = Promotion.objects.create(
        name="Promotion",
    )
    promotion.rules.create(
        name="Percentage promotion rule",
        promotion=promotion,
        catalogue_predicate={
            "productPredicate": {
                "ids": [graphene.Node.to_global_id("Product", product.id)]
            }
        },
        reward_value_type=RewardValueType.PERCENTAGE,
        reward_value=Decimal("5.0"),
    )

    # when
    update_products_discounted_prices_of_promotion_task(promotion.id)

    # then
    update_products_discounted_prices_mock.assert_called_once()
    args, kwargs = update_products_discounted_prices_mock.call_args

    assert len(args[0]) == 1
    assert {id for id in args[0]} == {product.id}


@patch(
    "saleor.product.tasks.update_products_discounted_prices_for_promotion_task.delay"
)
def test_update_products_discounted_prices_of_promotion_task_discount_does_not_exist(
    update_product_prices_mock, caplog
):
    # given
    caplog.set_level(logging.WARNING)
    promotion_id = -1

    # when
    update_products_discounted_prices_of_promotion_task(promotion_id)

    # then
    update_product_prices_mock.assert_not_called()
    assert f"Cannot find promotion with id: {promotion_id}" in caplog.text


@patch("saleor.product.tasks.DISCOUNTED_PRODUCT_BATCH", 1)
@patch("saleor.product.utils.variant_prices.update_discounted_prices_for_promotion")
def test_update_products_discounted_prices_for_promotion_task(
    update_products_discounted_prices_mock,
    product_list,
):
    # given
    ids = [product.id for product in product_list]

    # when
    update_products_discounted_prices_for_promotion_task(ids)

    # then
    update_products_discounted_prices_mock.call_count == len(ids)


@patch("saleor.product.tasks.update_products_discounted_price")
def test_update_product_discounted_price_task(update_product_price_mock, product):
    # when
    update_product_discounted_price_task(product.id)

    # then
    update_product_price_mock.assert_called_once_with([product])


@patch("saleor.product.tasks.update_products_discounted_price")
def test_update_product_discounted_price_task_product_does_not_exist(
    update_product_price_mock, caplog
):
    # given
    caplog.set_level(logging.WARNING)
    product_id = -1

    # when
    update_product_discounted_price_task(product_id)

    # then
    update_product_price_mock.assert_not_called()
    assert f"Cannot find product with id: {product_id}" in caplog.text


@patch("saleor.product.tasks._update_variants_names")
def test_update_variants_names(
    update_variants_names_mock, product_type, size_attribute
):
    # when
    update_variants_names(product_type.id, [size_attribute.id])

    # then
    args, _ = update_variants_names_mock.call_args
    assert args[0] == product_type
    assert {arg.pk for arg in args[1]} == {size_attribute.pk}


@patch("saleor.product.tasks.update_products_discounted_prices_of_sale")
def test_update_variants_names_product_type_does_not_exist(
    update_variants_names_mock, caplog
):
    # given
    caplog.set_level(logging.WARNING)
    product_type_id = -1

    # when
    update_variants_names(product_type_id, [])

    # then
    update_variants_names_mock.assert_not_called()
    assert f"Cannot find product type with id: {product_type_id}" in caplog.text


def test_get_preorder_variants_to_clean(
    variant,
    preorder_variant_global_threshold,
    preorder_variant_channel_threshold,
    preorder_variant_global_and_channel_threshold,
):
    preorder_variant_before_end_date = preorder_variant_channel_threshold
    preorder_variant_before_end_date.preorder_end_date = timezone.now() + timedelta(
        days=1
    )
    preorder_variant_before_end_date.save(update_fields=["preorder_end_date"])

    preorder_variant_after_end_date = preorder_variant_global_and_channel_threshold
    preorder_variant_after_end_date.preorder_end_date = timezone.now() - timedelta(
        days=1
    )
    preorder_variant_after_end_date.save(update_fields=["preorder_end_date"])

    variants_to_clean = _get_preorder_variants_to_clean()
    assert len(variants_to_clean) == 1
    assert variants_to_clean[0] == preorder_variant_after_end_date


def test_update_products_search_vector_task(product):
    # given
    product.search_index_dirty = True
    product.save(update_fields=["search_index_dirty"])

    # when
    update_products_search_vector_task()
    product.refresh_from_db(fields=["search_index_dirty"])

    # then
    assert product.search_index_dirty is False
