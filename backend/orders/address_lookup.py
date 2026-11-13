"""Explicit, cached address lookup for checkout using a configurable Photon server."""
import hashlib
import json
from decimal import Decimal, InvalidOperation
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from rest_framework.exceptions import APIException, ValidationError

SALT = "orders.checkout-address"


class AddressLookupUnavailable(APIException):
    status_code = 503
    default_detail = "Address lookup is temporarily unavailable. Please try again."


def search_addresses(query):
    key = "checkout-address:" + hashlib.sha256(query.casefold().encode()).hexdigest()
    results = cache.get(key)
    if results is not None:
        return results
    # An explicit search only: no requests on every keypress.
    if not cache.add("checkout-address-request", True, timeout=1):
        raise ValidationError({"detail": "Please wait a moment before searching again."})
    params = urlencode({"q": query, "lat": 45.5017, "lon": -73.5673,
                        "bbox": "-74.1,45.3,-73.3,45.8", "limit": 5, "lang": "en"})
    endpoint = settings.ADDRESS_LOOKUP_URL
    request = Request(f"{endpoint}?{params}", headers={
        "User-Agent": "FiveLeafClover/1.0 (https://github.com/sofia-ssanchez/foodDelivery)",
        "Accept": "application/json",
    })
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.load(response)
        results = []
        for feature in payload["features"]:
            props = feature["properties"]
            # Require a building address rather than silently using a street/city centre.
            if not props.get("housenumber") or not props.get("street"):
                continue
            longitude, latitude = (Decimal(str(v)) for v in feature["geometry"]["coordinates"][:2])
            if not (Decimal("45.3") <= latitude <= Decimal("45.8") and Decimal("-74.1") <= longitude <= Decimal("-73.3")):
                continue
            label = ", ".join(str(v) for v in (
                f'{props["housenumber"]} {props["street"]}', props.get("city") or props.get("district"),
                props.get("state"), props.get("postcode"), props.get("country"),
            ) if v)
            result = {"address": label, "latitude": str(latitude.quantize(Decimal("0.000001"))),
                      "longitude": str(longitude.quantize(Decimal("0.000001")))}
            if not any(existing["address"] == label for existing in results):
                results.append(result)
    except (URLError, TimeoutError, OSError, ValueError, KeyError, TypeError, InvalidOperation):
        raise AddressLookupUnavailable() from None
    cache.set(key, results, timeout=86400)
    return results


def read_checkout_address(token, customer_id):
    try:
        location = signing.loads(token, salt=SALT, max_age=3600)
        if location["customer_id"] != customer_id:
            raise ValueError()
        return location
    except (signing.BadSignature, KeyError, ValueError, TypeError):
        raise ValidationError({"detail": "Find and select your delivery address at checkout before placing the order."}) from None
