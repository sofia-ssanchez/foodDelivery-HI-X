"""Repeatable local demo baseline with orders across the delivery lifecycle."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.exceptions import PermissionDenied

from delivery.models import Courier, DeliveryAssignment
from pricing.models import RefundLedgerEntry, RefundRequest, OrderLedger
from .models import Order, OrderLine, OrderStatusEvent, Restaurant, MenuItem


def demo_enabled():
    return settings.DEBUG and (settings.BASE_DIR / '.demo-enabled').exists()


@transaction.atomic
def reset_demo():
    if not demo_enabled():
        raise PermissionDenied('Local demo mode is not enabled.')
    # Delete dependent records first; keep baseline user IDs so open tabs stay logged in.
    for model in (RefundLedgerEntry, RefundRequest, OrderLedger, DeliveryAssignment,
                  OrderStatusEvent, OrderLine, Order, MenuItem, Restaurant, Courier):
        model.objects.all().delete()
    User = get_user_model()
    names = ['customer1', 'customer2', 'customer3', 'customer4', 'customer5', 'customer6', 'courier1', 'courier2', 'restaurant1', 'restaurant2', 'restaurant3', 'restaurant4', 'restaurant5', 'restaurant6', 'operator1']
    User.objects.exclude(username__in=names).delete()
    users = {}
    for name in names:
        role = name[:-1]
        user, _ = User.objects.get_or_create(username=name)
        user.role = role
        user.first_name = name.capitalize()
        user.last_name = ''
        user.email = f'{name}@demo.example'
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        user.is_available = role == 'courier'
        user.latitude = user.longitude = None
        user.delivery_latitude = user.delivery_longitude = None
        user.set_password('12345678')
        user.save()
        users[name] = user
    menus = [
        ('Green Garden', '45.497200', '-73.578900', [
            ('Vegan Burger', '12.00'), ('Falafel Wrap', '10.50'),
            ('Quinoa Salad', '11.00'), ('Tofu Bowl', '14.00'),
            ('Sweet Potato Fries', '5.50'), ('Lentil Soup', '7.50'),
            ('Chocolate Brownie', '6.00'), ('Berry Smoothie', '6.50')]),
        ('Vegan Corner', '45.523100', '-73.582600', [
            ('Vegan Poutine', '13.50'), ('Mushroom Burger', '12.50'),
            ('Chickpea Curry', '15.00'), ('Tempeh Sandwich', '11.50'),
            ('Garden Salad', '8.00'), ('Roasted Potatoes', '5.00'),
            ('Vegan Cheesecake', '6.50'), ('Lemonade', '4.00')]),
        ('Plateau Pizza', '45.530500', '-73.583200', [
            ('Margherita Pizza', '16.00'), ('Mushroom Pizza', '18.00'),
            ('Pesto Pizza', '18.50'), ('Roasted Pepper Pizza', '17.50'),
            ('Garlic Bread', '5.50'), ('Caesar Salad', '8.00'),
            ('Tiramisu', '7.00'), ('Sparkling Lemonade', '4.50')]),
        ('Verdun Bowl', '45.459000', '-73.572400', [
            ('Teriyaki Tofu Bowl', '15.00'), ('Sesame Noodle Bowl', '14.00'),
            ('Kimchi Rice Bowl', '15.50'), ('Miso Mushroom Bowl', '16.00'),
            ('Edamame', '5.00'), ('Vegetable Dumplings', '7.50'),
            ('Mango Pudding', '6.00'), ('Iced Green Tea', '4.00')]),
        ('Rosemont Tacos', '45.550000', '-73.579000', [
            ('Black Bean Tacos', '12.00'), ('Mushroom Tacos', '13.50'),
            ('Roasted Corn Burrito', '14.00'), ('Sweet Potato Quesadilla', '13.00'),
            ('Chips and Guacamole', '7.00'), ('Mexican Rice', '5.00'),
            ('Churros', '6.00'), ('Hibiscus Iced Tea', '4.50')]),
        ('Lachine Bistro', '45.433000', '-73.677000', [
            ('Lentil Shepherds Pie', '17.00'), ('Vegetable Pot Pie', '16.50'),
            ('Grilled Vegetable Sandwich', '13.00'), ('Herb Gnocchi', '18.00'),
            ('Tomato Soup', '7.00'), ('Bistro Fries', '5.50'),
            ('Apple Crumble', '7.00'), ('House Iced Tea', '4.00')]),
    ]
    for index, (name, lat, lng, menu) in enumerate(menus, 1):
        restaurant = Restaurant.objects.create(name=name, owner=users[f'restaurant{index}'],
            status='paused' if index == 6 else 'open', latitude=lat, longitude=lng)
        MenuItem.objects.bulk_create([MenuItem(restaurant=restaurant, name=item, price=price,
            status='available') for item, price in menu])
        if index <= 2:
            Courier.objects.update_or_create(user=users[f'courier{index}'], defaults={'status': 'idle', 'latitude': lat, 'longitude': lng})
    count = seed_demo_orders()
    return {'detail': 'Demo reset complete.', 'restaurants': len(menus), 'couriers': 2, 'customers': 6, 'orders': count}


@transaction.atomic
def seed_demo_orders():
    """Add sample orders with matching timestamps, history, assignments and charges."""
    from datetime import timedelta
    from django.utils import timezone
    from .event_services import record_order_status_event
    from pricing.services import record_order_ledger

    if not demo_enabled():
        raise PermissionDenied('Local demo mode is not enabled.')
    User = get_user_model()
    for number in range(3, 7):
        user, created = User.objects.get_or_create(username=f'customer{number}', defaults={'role': 'customer'})
        if created:
            user.set_password('12345678')
            user.save()
    restaurants = [Restaurant.objects.get(owner__username=f'restaurant{i}') for i in range(1, 7)]
    couriers = [Courier.objects.get(user__username=f'courier{i}') for i in (1, 2)]
    if DeliveryAssignment.objects.filter(courier__in=couriers, status__in=['offered', 'accepted']).exists():
        raise ValueError('Demo couriers already have active deliveries; use Reset demo to restore the seeded baseline.')
    destinations = [
        ('1455 Boulevard de Maisonneuve Ouest, Montreal', '45.497300', '-73.578900'),
        ('845 Rue Sherbrooke Ouest, Montreal', '45.504800', '-73.577200'),
        ('175 Rue Sainte-Catherine Ouest, Montreal', '45.508200', '-73.566400'),
        ('475 Avenue du President-Kennedy, Montreal', '45.508600', '-73.571000'),
        ('350 Rue Saint-Paul Est, Montreal', '45.509500', '-73.551500'),
        ('1200 Rue de Bleury, Montreal', '45.505900', '-73.564200'),
    ]
    # Vary placed + accepted counts across both sides of each map threshold.
    queued_counts = [(1, 1), (2, 2), (4, 3), (0, 0), (3, 2), (1, 0)]
    # Keep preparation, pickup queues, and completed history available to demo.
    # Only two couriers exist: reserve one for an offer and one for a pickup.
    scenarios = [
        (status, (restaurant_index * 3 + sample) % 6 + 1, restaurant_index)
        for status in ('delivered', 'ready', 'preparing', 'accepted', 'placed')
        for restaurant_index in range(len(restaurants))
        for sample in range(
            queued_counts[restaurant_index][0] if status == 'placed' else
            queued_counts[restaurant_index][1] if status == 'accepted' else 3
        )
    ]
    scenarios.insert(3 * len(restaurants), ('picked_up', 2, 1))
    offered_couriers = set()
    stages = ['placed', 'accepted', 'preparing', 'ready', 'picked_up', 'delivered']
    for index, (status, customer_number, restaurant_index) in enumerate(scenarios):
        restaurant = restaurants[restaurant_index]
        courier = couriers[restaurant_index % len(couriers)]
        customer = User.objects.get(username=f'customer{customer_number}')
        address, lat, lng = destinations[customer_number - 1]
        start = timezone.now() - timedelta(minutes=60 + (len(scenarios) - index) * 40)
        final_stage = stages.index(status)
        order = Order.objects.create(customer=customer, restaurant=restaurant, status=status,
            delivery_address=address, delivery_latitude=lat, delivery_longitude=lng,
            ready_at=start + timedelta(minutes=15) if final_stage >= 3 else None,
            picked_up_at=start + timedelta(minutes=20) if final_stage >= 4 else None,
            delivered_at=start + timedelta(minutes=30) if final_stage >= 5 else None)
        Order.objects.filter(pk=order.pk).update(created_at=start)
        order.created_at = start
        items = list(restaurant.menu_items.order_by('id'))
        for item, quantity in ((items[index % 4], 1), (items[4 + index % 4], 2)):
            OrderLine.objects.create(order=order, menu_item=item, quantity=quantity, unit_price=item.price)
        for step, stage in enumerate(stages[:final_stage + 1]):
            actor = customer if step == 0 else courier.user if step >= 4 else restaurant.owner
            event = record_order_status_event(order, stages[step - 1] if step else '', stage, actor)
            OrderStatusEvent.objects.filter(pk=event.pk).update(timestamp=start + timedelta(minutes=[0, 3, 5, 15, 20, 30][step]))
        should_offer = status == 'ready' and restaurant_index == 0 and courier.pk not in offered_couriers
        if status in ('picked_up', 'delivered') or should_offer:
            if should_offer:
                offered_couriers.add(courier.pk)
            assignment = DeliveryAssignment.objects.create(order=order, courier=courier,
                status={'ready': 'offered', 'picked_up': 'accepted', 'delivered': 'completed'}[status],
                accepted_at=start + timedelta(minutes=17) if final_stage >= 4 else None,
                picked_up_at=order.picked_up_at, delivered_at=order.delivered_at)
            DeliveryAssignment.objects.filter(pk=assignment.pk).update(offered_at=order.ready_at)
        if status == 'delivered':
            record_order_ledger(order)
            OrderLedger.objects.filter(order=order).update(finalized_at=order.delivered_at)
        if status == 'picked_up':
            Courier.objects.filter(pk=courier.pk).update(status='carrying', latitude='45.516000', longitude='-73.579000')
    return len(scenarios)
