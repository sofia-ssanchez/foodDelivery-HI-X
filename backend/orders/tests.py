from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from delivery.commands import ChangeDutyCommand, create_delivery_offer
from delivery.models import DeliveryAssignment
from pricing.models import OrderLedger
from .models import MenuItem, Order, OrderLine, Restaurant


class DashboardIntegrationTests(APITestCase):
    def setUp(self):
        users = get_user_model().objects
        self.courier = users.create_user(username="courier", role="courier")
        self.other = users.create_user(username="other", role="courier")
        self.customer = users.create_user(username="customer", role="customer")
        self.owner = users.create_user(username="restaurant", role="restaurant")
        self.restaurant = Restaurant.objects.create(name="Test", owner=self.owner, latitude=45, longitude=-73)
        self.order = Order.objects.create(customer=self.customer, restaurant=self.restaurant, status="ready")
        item = MenuItem.objects.create(restaurant=self.restaurant, name="Soup", price="8.00")
        OrderLine.objects.create(order=self.order, menu_item=item, quantity=2, unit_price=item.price)
        self.client.force_authenticate(self.courier)
        ChangeDutyCommand(self.courier, True).execute()
        self.assignment = create_delivery_offer(order_id=self.order.id, courier_id=self.courier.courier_profile.id)

    def test_activity_contract_and_complete_frontend_flow(self):
        data = self.client.get("/api/delivery/me/").data
        self.assertEqual(data["courier"]["status"], "idle")
        self.assertEqual(data["history"], [])
        self.assertEqual(data["offers"][0]["order_id"], self.order.id)
        self.assertEqual(data["offers"][0]["customer_name"], "customer")
        self.assertEqual(data["offers"][0]["lines"][0]["quantity"], 2)
        offer_url = f"/api/delivery/offers/{self.assignment.id}/accept/"
        self.assertEqual(self.client.post(offer_url).status_code, 200)
        pickup_url = f"/api/delivery/assignments/{self.assignment.id}/pickup/"
        deliver_url = f"/api/delivery/assignments/{self.assignment.id}/deliver/"
        self.assertEqual(self.client.post(deliver_url).status_code, 409)
        self.order.refresh_from_db()
        self.assertIsNone(self.order.delivered_at)
        self.assertEqual(self.client.post(pickup_url).status_code, 200)
        self.order.refresh_from_db()
        self.assignment.refresh_from_db()
        pickup_time = self.order.picked_up_at
        self.assertIsNotNone(pickup_time)
        self.assertEqual(pickup_time, self.assignment.picked_up_at)
        self.assertEqual(self.client.post(pickup_url).status_code, 409)
        self.assertEqual(self.client.post(deliver_url).status_code, 200)
        self.order.refresh_from_db()
        self.assignment.refresh_from_db()
        delivery_time = self.order.delivered_at
        self.assertEqual(delivery_time, self.assignment.delivered_at)
        self.assertGreaterEqual(delivery_time, pickup_time)
        self.assertEqual(self.client.post(deliver_url).status_code, 409)
        self.order.refresh_from_db()
        self.assertEqual(self.order.delivered_at, delivery_time)
        data = self.client.get("/api/delivery/me/").data
        self.assertIsNone(data["active_assignment"])
        self.assertEqual(data["history"][0]["status"], "completed")
        self.assertEqual(OrderLedger.objects.filter(order=self.order).count(), 1)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get("/api/delivery/me/").data["history"], [])

    def test_restaurant_cannot_bypass_courier_pickup(self):
        self.client.force_authenticate(self.owner)
        response = self.client.patch(f"/api/restaurant/orders/{self.order.id}/status/", {
            "status": "picked_up", "expected_status": "ready",
        })
        self.assertEqual(response.status_code, 400)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "ready")

    def test_imported_carrying_order_with_unknown_pickup_time_can_finish(self):
        self.assignment.status = DeliveryAssignment.Status.ACCEPTED
        self.assignment.save()
        profile = self.courier.courier_profile
        profile.status = "carrying"
        profile.save()
        self.order.status = "picked_up"
        self.order.save()
        response = self.client.post(f"/api/delivery/assignments/{self.assignment.id}/deliver/")
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertIsNone(self.order.picked_up_at)
        self.assertIsNotNone(self.order.delivered_at)
