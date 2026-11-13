"""Repeatable random sample Montreal destinations for local seed data."""
from random import Random

MONTREAL_ADDRESSES = (
    ("1455 Boulevard de Maisonneuve Ouest, Montreal", "45.497300", "-73.578900"),
    ("845 Rue Sherbrooke Ouest, Montreal", "45.504800", "-73.577200"),
    ("175 Rue Sainte-Catherine Ouest, Montreal", "45.508200", "-73.566400"),
    ("475 Avenue du President-Kennedy, Montreal", "45.508600", "-73.571000"),
    ("350 Rue Saint-Paul Est, Montreal", "45.509500", "-73.551500"),
    ("1200 Rue de Bleury, Montreal", "45.505900", "-73.564200"),
)


def seed_customer_addresses(customers, *, overwrite=False):
    addresses = list(MONTREAL_ADDRESSES)
    Random(343).shuffle(addresses)
    for index, customer in enumerate(customers):
        if customer.delivery_address and not overwrite:
            continue
        address, latitude, longitude = addresses[index % len(addresses)]
        customer.delivery_address = address
        customer.delivery_unit = ""
        customer.delivery_latitude = latitude
        customer.delivery_longitude = longitude
        customer.save(update_fields=[
            "delivery_address", "delivery_unit", "delivery_latitude", "delivery_longitude",
        ])
