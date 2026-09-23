"""
P4 Store Agent — Tool Definitions
Three tools the LangGraph agent can call. Each reads a JSON file,
applies logic, and returns a structured dict. All errors are returned
as {"error": "..."} so the agent can reason about them rather than crash.
"""

import json
from datetime import date, timedelta
from pathlib import Path
from langchain_core.tools import tool

DATA = Path(__file__).parent / "data"


def _load(filename: str) -> dict:
    with open(DATA / filename, encoding="utf-8") as f:
        return json.load(f)


@tool
def check_stock(product_name: str, color: str, size: str, quantity: int) -> dict:
    """
    Check whether a product is available in the requested quantity.

    Args:
        product_name: Product type, e.g. 'Classic Cotton Shirt', 'Slim Fit Jeans',
                      'Polo T-Shirt', 'Pullover Hoodie', 'Bomber Jacket', 'Cargo Pants'
        color:        Color variant, e.g. 'Blue', 'Black', 'White', 'Navy', 'Olive'
        size:         Size code — S, M, L, or XL
        quantity:     How many units the customer wants

    Returns a dict with:
        sku, in_stock (bool), available (int), requested (int),
        unit_price (int, INR), and an optional 'error' key.
    """
    try:
        inventory = _load("inventory.json")
        products = inventory["products"]

        # Normalise inputs so "shirt" matches "Classic Cotton Shirt", etc.
        name_lower = product_name.lower()
        color_lower = color.lower()
        size_upper = size.upper()

        # Flexible name matching
        NAME_MAP = {
            "shirt": "classic cotton shirt",
            "polo":  "polo t-shirt",
            "tshirt": "polo t-shirt",
            "t-shirt": "polo t-shirt",
            "jeans": "slim fit jeans",
            "hoodie": "pullover hoodie",
            "jacket": "bomber jacket",
            "cargo": "cargo pants",
            "pants": "cargo pants",
        }
        for alias, canonical in NAME_MAP.items():
            if alias in name_lower:
                name_lower = canonical
                break

        match = next(
            (p for p in products
             if p["name"].lower() == name_lower
             and p["color"].lower() == color_lower
             and p["size"] == size_upper),
            None,
        )

        if match is None:
            return {
                "error": (
                    f"No product found matching '{product_name}' / {color} / {size}. "
                    "Check that name, color and size are all valid."
                )
            }

        available = match["stock"]
        return {
            "sku":        match["sku"],
            "product":    match["name"],
            "color":      match["color"],
            "size":       match["size"],
            "in_stock":   available >= quantity,
            "available":  available,
            "requested":  quantity,
            "unit_price": match["price"],
        }

    except Exception as e:
        return {"error": f"check_stock failed: {e}"}


@tool
def price_order(sku: str, quantity: int, unit_price: int, first_order: bool = False) -> dict:
    """
    Calculate the final price after applying the best available discount.

    Args:
        sku:         Product SKU returned by check_stock, e.g. 'SHIRT-BLUE-M'
        quantity:    Number of units to price
        unit_price:  Unit price in INR returned by check_stock
        first_order: True if the customer is placing their first order

    Returns a dict with:
        base_total, discount_id, discount_label, discount_percent,
        discount_amount, final_total (all in INR).
    """
    try:
        data = _load("discounts.json")
        rules = data["rules"]

        base_total = unit_price * quantity
        best_rule = None
        best_pct = 0

        for rule in rules:
            pct = rule["discount_percent"]
            if pct <= best_pct:
                continue

            if rule["type"] == "bulk":
                min_q = rule["min_quantity"]
                max_q = rule["max_quantity"]
                if quantity >= min_q and (max_q is None or quantity <= max_q):
                    best_rule, best_pct = rule, pct

            elif rule["type"] == "sku" and sku in rule["skus"]:
                best_rule, best_pct = rule, pct

            elif rule["type"] == "customer" and first_order:
                best_rule, best_pct = rule, pct

        discount_amount = round(base_total * best_pct / 100) if best_rule else 0
        return {
            "sku":              sku,
            "quantity":         quantity,
            "unit_price":       unit_price,
            "base_total":       base_total,
            "discount_id":      best_rule["id"] if best_rule else None,
            "discount_label":   best_rule["description"] if best_rule else "No discount applicable",
            "discount_percent": best_pct,
            "discount_amount":  discount_amount,
            "final_total":      base_total - discount_amount,
        }

    except Exception as e:
        return {"error": f"price_order failed: {e}"}


@tool
def delivery_eta(pincode: str, shipping_type: str = "standard") -> dict:
    """
    Get the estimated delivery date and shipping cost for a pincode.

    Args:
        pincode:       6-digit Indian pincode, e.g. '560001'
        shipping_type: 'standard' (default) or 'express'

    Returns a dict with:
        pincode, zone, zone_label, shipping_type, cost (INR),
        days, estimated_delivery (YYYY-MM-DD), and an optional 'error' key.
    """
    try:
        data = _load("shipping.json")
        zones = data["zones"]
        fallback = data.get("fallback_zone", "remote")

        pincode = pincode.strip()
        if not pincode.isdigit() or len(pincode) != 6:
            return {"error": f"'{pincode}' is not a valid 6-digit Indian pincode."}

        shipping_type = shipping_type.lower()
        if shipping_type not in ("standard", "express"):
            shipping_type = "standard"

        # Find which zone the pincode belongs to
        zone_key = None
        for key, zone_data in zones.items():
            if pincode in zone_data.get("pincodes", []):
                zone_key = key
                break

        if zone_key is None:
            return {"error": f"Pincode '{pincode}' is not in our delivery network. Please check and try again."}

        zone = zones[zone_key]
        days_key  = f"{shipping_type}_days"
        cost_key  = f"{shipping_type}_cost"
        days = zone[days_key]
        cost = zone[cost_key]
        eta  = (date.today() + timedelta(days=days)).strftime("%d %b %Y")

        return {
            "pincode":            pincode,
            "zone":               zone_key,
            "zone_label":         zone["label"],
            "shipping_type":      shipping_type,
            "cost":               cost,
            "days":               days,
            "estimated_delivery": eta,
        }

    except Exception as e:
        return {"error": f"delivery_eta failed: {e}"}
