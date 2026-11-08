from rest_framework import serializers
from .models import RefundRequest


class RefundRequestCreateSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    reason = serializers.ChoiceField(choices=RefundRequest.Reason.choices)
    details = serializers.CharField(required=False, allow_blank=True)
    requested_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True,
    )


class RefundDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(
        choices=["approve", "reject"]
    )

    approved_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True,
    )

    decision_notes = serializers.CharField(
        required=False,
        allow_blank=True,
    )