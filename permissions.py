from django.utils import timezone
from django.db.models import Q
from rest_framework.permissions import BasePermission

from apps.payment.constants import SUBSCRIPTION_STATUS_ACTIVE
from apps.payment.models import UserSubscription


class IsActiveGSTSubscriber(BasePermission):
    """
    Allows access only to users with an active GST subscription for the GST app.
    """

    message = "You currently do not have an active subscription plan. Please subscribe to access GST features."

    def has_permission(self, request, view):
        now = timezone.now()
        return (
            UserSubscription.objects.select_related("plan__app")
            .filter(
                user=request.user,
                status=SUBSCRIPTION_STATUS_ACTIVE,
                plan__isnull=False,
                plan__app__name="GST",
            )
            .filter(Q(end_date__isnull=True) | Q(end_date__gt=now))
            .exists()
        )
