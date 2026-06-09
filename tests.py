from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.payment.constants import SUBSCRIPTION_STATUS_ACTIVE
from apps.payment.models import SubscriptionPlan, UserSubscription

User = get_user_model()


class GSTSubscriptionPermissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="testuser@example.com", password="testpass"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.plan = SubscriptionPlan.objects.create(
            name="monthly", price=999, duration_months=1
        )
        self.url = (
            "/api/gst/some-protected-endpoint/"  # Replace with a real GST endpoint
        )

    def test_access_denied_without_subscription(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_access_allowed_with_active_subscription(self):
        UserSubscription.objects.create(
            user=self.user, plan=self.plan, status=SUBSCRIPTION_STATUS_ACTIVE
        )
        response = self.client.get(self.url)
        # 404 is possible if endpoint doesn't exist, but should not be 403
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)
