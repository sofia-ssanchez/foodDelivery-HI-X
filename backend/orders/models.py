from django.conf import settings
from django.db import models
from .states import get_order_state

class Restaurant(models.Model) :

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        PAUSED = 'paused', 'Paused'
        CLOSED = 'closed', 'Closed'

    name = models.CharField(max_length=150)

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.OPEN,
    )

    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
    )

    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, #refernces custom User model created in ./accounts/models.py
        on_delete=models.PROTECT,
        related_name='restaurants',
    )

    def __str__(self):
       return self.name

class MenuItem(models.Model) :

    class Status(models.TextChoices):
        AVAILABLE = 'available', 'Available'
        SOLD_OUT = 'sold_out', 'Sold Out'

    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name='menu_items',
    )

    name = models.CharField(max_length=150)

    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["restaurant", "name"],
                name="unique_menu_item_per_restaurant",
            )
        ]

    def __str__(self):
        return self.name

class Order(models.Model) :

    @property
    def state(self):
        return get_order_state(self.status)

    def transition(self, target_status):
        next_state = self.state.transition(target_status)
        self.status = next_state.status
        return next_state

    class Status(models.TextChoices):
        PLACED = 'placed', 'Placed'
        ACCEPTED = 'accepted', 'Accepted'
        REJECTED = 'rejected', 'Rejected'
        PREPARING = 'preparing', 'Preparing'
        READY = 'ready', 'Ready'
        PICKED_UP = 'picked_up', 'Picked up'
        CANCELLED = 'cancelled', 'Cancelled'
        DELIVERED = 'delivered', 'Delivered'
        PARTIALLY_REFUNDED = 'partially_refunded', 'Partially Refunded'
        REFUNDED = 'refunded', 'Refunded'

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='orders',
    )

    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.PROTECT,
        related_name='orders',
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLACED,
    )

    picked_up_at = models.DateTimeField(null=True, blank=True, editable=False)
    delivered_at = models.DateTimeField(null=True, blank=True, editable=False)

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    ready_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Orders {self.id} - {self.status}"

class OrderStatusEvent(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name="status_events",
    )

    transition_number = models.PositiveIntegerField()

    event_id = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
    )

    from_status = models.CharField(
        max_length=20,
        blank=True,
    )

    to_status = models.CharField(
        max_length=20,
    )

    timestamp = models.DateTimeField(auto_now_add=True)

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_status_events",
    )

    actor_username = models.CharField(
        max_length=150,
        blank=True,
    )

    actor_role = models.CharField(
        max_length=30,
        blank=True,
    )

    class Meta:
        ordering = ["transition_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "transition_number"],
                name="unique_order_transition_number",
            )
        ]

    def save(self, *args, **kwargs):
        if not self.event_id and self.order_id and self.transition_number:
            self.event_id = f"evt-{self.order_id}-{self.transition_number}"

        super().save(*args, **kwargs)

    def __str__(self):
        return self.event_id

class OrderLine(models.Model) :

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='lines'
    )

    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.PROTECT,
        related_name='order_lines',
    )

    quantity = models.PositiveIntegerField()

    unit_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
    )

    def __str__(self):
        return f"{self.quantity} x {self.menu_item.name}"
