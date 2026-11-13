from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from pricing.services import record_order_ledger
from orders.demo_addresses import seed_customer_addresses
from orders.models import Order, OrderLine, Restaurant, MenuItem
import os


class Command(BaseCommand):
    help = "Populate the database with initial project data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--restore-baseline",
            action="store_true",
            help="Restore the standard values of seeded records.",
        )

    def restore_record(self, record, created, restore_baseline, defaults):
        if restore_baseline and not created:
            for field, value in defaults.items():
                setattr(record, field, value)

            record.save()
            self.stdout.write(f"Restored {record._meta.verbose_name}: {record}")

    def handle(self, *args, **options):
        restore_baseline = options["restore_baseline"]

        User = get_user_model()


        test_accounts = [
            ("testCustomer1", "customer"),
            ("testCustomer2", "customer"),

            ("testRestaurant1", "restaurant"),
            ("testRestaurant2", "restaurant"),
            ("testRestaurant3", "restaurant"),

            ("testCourier1", "courier"),
            ("testOperator1", "operator"),
        ]

        for username, role in test_accounts:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"role": role},
            )

            if created:
                user.set_password("password")
                user.save()
                self.stdout.write(f"Created: {username}")
            else:
                self.stdout.write(f"Already exists: {username}")

        self.stdout.write(
            self.style.SUCCESS("Test accounts are ready!")
        )


        seed_customer_addresses(
            User.objects.filter(username__in=[name for name, role in test_accounts if role == "customer"]).order_by("username"),
            overwrite=restore_baseline,
        )

        # Shared admin account
        admin_password = os.environ.get("ADMIN_PASSWORD")

        if admin_password:
            admin, created = User.objects.get_or_create(
                username="admin",
                defaults={
                    "role": "operator",
                    "is_staff": True,
                    "is_superuser": True,
                },
            )

            if created:
                admin.set_password(admin_password)
                admin.save()
                self.stdout.write("Created shared admin.")
            else:
                self.stdout.write(
                    "admin already exists; credentials unchanged."
                )
        else:
            self.stdout.write(
                "ADMIN_PASSWORD not set; skipping admin."
            )

        # Restaurant and menu configurations
        restaurants_data = [
            {
                "name": "Green Garden",
                "owner_username": "testRestaurant1",
                "status": Restaurant.Status.OPEN,
                "latitude": "45.501700",
                "longitude": "-73.567300",
                "menu": [
                    ("Vegan Burger", "12.00", MenuItem.Status.AVAILABLE),
                    ("Falafel Wrap", "10.50", MenuItem.Status.AVAILABLE),
                    ("Quinoa Salad", "11.00", MenuItem.Status.AVAILABLE),
                    ("Sweet Potato Fries", "5.50", MenuItem.Status.AVAILABLE),
                    ("Chocolate Brownie", "6.00", MenuItem.Status.SOLD_OUT),
                ],
            },
            {
                "name": "Vegan Corner",
                "owner_username": "testRestaurant2",
                "status": Restaurant.Status.PAUSED,
                "latitude": "45.508800",
                "longitude": "-73.587800",
                "menu": [
                    ("Vegan Poutine", "13.50", MenuItem.Status.AVAILABLE),
                    ("Tofu Bowl", "14.00", MenuItem.Status.AVAILABLE),
                    ("Mushroom Burger", "12.50", MenuItem.Status.AVAILABLE),
                    ("Lentil Soup", "7.50", MenuItem.Status.AVAILABLE),
                    ("Vegan Cheesecake", "6.50", MenuItem.Status.SOLD_OUT),
                ],
            },
            {
                "name": "Plant Paradise",
                "owner_username": "testRestaurant3",
                "status": Restaurant.Status.CLOSED,
                "latitude": "45.520000",
                "longitude": "-73.560000",
                "menu": [
                    ("Chickpea Curry", "15.00", MenuItem.Status.AVAILABLE),
                    ("Tempeh Sandwich", "11.50", MenuItem.Status.AVAILABLE),
                    ("Avocado Toast", "9.00", MenuItem.Status.AVAILABLE),
                    ("Roasted Vegetable Bowl", "13.00", MenuItem.Status.AVAILABLE),
                    ("Berry Smoothie", "6.00", MenuItem.Status.SOLD_OUT),
                ],
            },
        ]

        # Create or restore restaurants
        for data in restaurants_data:
            owner = User.objects.get(
                username=data["owner_username"]
            )

            defaults = {
                "status": data["status"],
                "latitude": data["latitude"],
                "longitude": data["longitude"],
                "owner": owner,
            }

            restaurant, created = Restaurant.objects.get_or_create(
                name=data["name"],
                defaults=defaults,
            )

            if created:
                self.stdout.write(
                    f"Created restaurant: {restaurant.name}"
                )
            else:
                self.stdout.write(
                    f"Restaurant already exists: {restaurant.name}"
                )

            self.restore_record(
                restaurant,
                created,
                restore_baseline,
                defaults,
            )

            # Create menu items for this restaurant
            for name, price, status in data["menu"]:
                item_defaults = {
                    "price": price,
                    "status": status,
                }

                item, item_created = MenuItem.objects.get_or_create(
                    restaurant=restaurant,
                    name=name,
                    defaults=item_defaults,
                )

                if item_created:
                    self.stdout.write(
                        f"Created menu item: {restaurant.name} - {name}"
                    )
                else:
                    self.stdout.write(
                        f"Menu item already exists: {restaurant.name} - {name}"
                    )

                self.restore_record(
                    item,
                    item_created,
                    restore_baseline,
                    item_defaults,
                )

        # Seed finalized orders for the operator ledger
        seeded_orders = [
            {
                "customer": "testCustomer1",
                "restaurant": "Green Garden",
                "status": Order.Status.DELIVERED,
                "items": [
                    ("Vegan Burger", 2),
                    ("Sweet Potato Fries", 1),
                ],
            },
            {
                "customer": "testCustomer2",
                "restaurant": "Vegan Corner",
                "status": Order.Status.DELIVERED,
                "items": [
                    ("Tofu Bowl", 1),
                    ("Vegan Poutine", 1),
                ],
            },
            {
                "customer": "testCustomer1",
                "restaurant": "Vegan Corner",
                "status": Order.Status.CANCELLED,
                "items": [
                    ("Mushroom Burger", 1),
                    ("Lentil Soup", 2),
                ],
            },
            {
                "customer": "testCustomer2",
                "restaurant": "Plant Paradise",
                "status": Order.Status.CANCELLED,
                "items": [
                    ("Chickpea Curry", 1),
                    ("Tempeh Sandwich", 1),
                ],
            },
            {
                "customer": "testCustomer2",
                "restaurant": "Green Garden",
                "status": Order.Status.DELIVERED,
                "items": [
                    ("Sweet Potato Fries", 1),
                ],
           },
        ]

        for data in seeded_orders:
            customer = User.objects.get(username=data["customer"])
            restaurant = Restaurant.objects.get(name=data["restaurant"])

            order, created = Order.objects.get_or_create(
                customer=customer,
                restaurant=restaurant,
                status=data["status"],
            )

            if created:
                self.stdout.write(
                    f"Created {data['status']} order #{order.id}"
                )
            else:
                self.stdout.write(
                    f"Order already exists: #{order.id}"
                )

            if created or restore_baseline or not order.delivery_address:
                order.delivery_address = customer.delivery_address
                order.delivery_unit = customer.delivery_unit
                order.delivery_latitude = customer.delivery_latitude
                order.delivery_longitude = customer.delivery_longitude
                order.save(update_fields=["delivery_address", "delivery_unit", "delivery_latitude", "delivery_longitude"])

            # Create the order lines if they don't already exist
            for item_name, quantity in data["items"]:
                menu_item = MenuItem.objects.get(
                    restaurant=restaurant,
                    name=item_name,
                )

                OrderLine.objects.get_or_create(
                    order=order,
                    menu_item=menu_item,
                    defaults={
                        "quantity": quantity,
                        "unit_price": menu_item.price,
                    },
                )

            # Make sure the finalized order has a ledger entry
            record_order_ledger(order)

        self.stdout.write(
            self.style.SUCCESS("Seeded finalized orders and ledger entries!")
        )

