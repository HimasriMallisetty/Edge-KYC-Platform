import hashlib
import hmac
import logging
import razorpay

from django.conf import settings

from .constants import STATUS_FAILED, STATUS_SUCCESS

exception_logger = logging.getLogger("exceptions")


class RazorpayClient:
    def __init__(self):
        self.key_id = settings.RAZORPAY_KEY_ID
        self.key_secret = settings.RAZORPAY_KEY_SECRET
        self.webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
        self.base_url = settings.RAZORPAY_BASE_URL
        self.client = razorpay.Client(auth=(self.key_id, self.key_secret))

    def create_order(self, transaction_id, amount, currency="INR", payment_capture=1):
        """Creates a Razorpay order."""
        data = {
            "amount": int(amount * 100),
            "currency": currency,
            "receipt": transaction_id,
            "payment_capture": payment_capture,
            "notes": {"transaction_id": transaction_id},
        }
        order = self.client.order.create(data)

        return order

    def verify_signature(self, order_id, payment_id, signature):
        try:
            key_secret = self.key_secret.encode()
            msg = f"{order_id}|{payment_id}".encode()
            generated_signature = hmac.new(key_secret, msg, hashlib.sha256).hexdigest()

            return STATUS_SUCCESS if generated_signature == signature else STATUS_FAILED

        except Exception as e:
            exception_logger.error(f"{e}", exc_info=True)
            return STATUS_FAILED

    def verify_webhook_signature(self, payload, received_signature):
        """Verify Razorpay webhook signature."""
        try:
            secret = self.webhook_secret.encode("utf-8")
            generated_signature = hmac.new(
                secret, payload.encode("utf-8"), hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(generated_signature, received_signature)
        except Exception as e:
            exception_logger.error(f"Signature verification error: {e}")
            return False

    def create_plan(
        self, plan_name, period, interval, amount, currency="INR", description=None
    ):
        """Creates a Razorpay plan for subscriptions."""
        data = {
            "period": period,  # 'monthly', 'yearly', etc.
            "interval": interval,  # 1, 3, 6, 12, etc.
            "item": {
                "name": plan_name,
                "amount": int(amount * 100),
                "currency": currency,
                "description": description or plan_name,
            },
        }
        plan = self.client.plan.create(data)
        return plan

    def create_subscription(
        self,
        plan_id,
        customer_notify=1,
        total_count=None,
        quantity=1,
        start_at=None,
        notes=None,
    ):
        """Creates a Razorpay subscription for a user."""
        data = {
            "plan_id": plan_id,
            "customer_notify": customer_notify,
            "quantity": quantity,
        }
        if total_count:
            data["total_count"] = total_count
        if start_at:
            data["start_at"] = start_at
        if notes:
            data["notes"] = notes
        subscription = self.client.subscription.create(data)
        
        return subscription

    def cancel_subscription(self, subscription_id):
        """Cancel a Razorpay subscription."""
        return self.client.subscription.cancel(subscription_id)

    def pause_subscription(self, subscription_id, pause_at_cycle_end=False):
        """Pause a Razorpay subscription. If pause_at_cycle_end is True, pause at the end of the current cycle."""
        data = {"pause_at_cycle_end": pause_at_cycle_end}
        return self.client.subscription.pause(subscription_id, data)

    def resume_subscription(self, subscription_id):
        """Resume a paused Razorpay subscription."""
        return self.client.subscription.resume(subscription_id)
