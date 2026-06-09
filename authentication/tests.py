from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from apps.authentication.models import User, UserVerifications

# Create your tests here.


class SignupProcessTestCase(TestCase):
    def setUp(self):
        self.signup_url = reverse("auth:signup")
        self.verify_email_otp_url = reverse("auth:verify-email-otp")
        self.verify_mobile_otp_url = reverse("auth:verify-mobile-otp")
        self.email = "testuser@example.com"
        self.phone = "1234567890"
        self.password = "testpassword123"
        self.signup_data = {
            "name": "Test User",
            "email": self.email,
            "phone": self.phone,
            "password": self.password,
            "confirmPassword": self.password,
        }

    def test_full_signup_and_otp_verification(self):
        # 1. Signup
        response = self.client.post(
            self.signup_url, self.signup_data, content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email=self.email)
        self.assertFalse(user.is_email_verified)
        self.assertFalse(user.is_mobile_verified)

        # 2. Get OTPs from DB (simulate user receiving them)
        email_otp_obj = UserVerifications.objects.filter(
            user=user, type="email", is_used=False
        ).latest("created_at")
        mobile_otp_obj = UserVerifications.objects.filter(
            user=user, type="mobile", is_used=False
        ).latest("created_at")
        email_otp = email_otp_obj.otp
        mobile_otp = mobile_otp_obj.otp

        # 3. Verify email OTP
        response = self.client.post(
            self.verify_email_otp_url,
            {"email": self.email, "otp": email_otp},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.is_email_verified)

        # 4. Verify mobile OTP
        response = self.client.post(
            self.verify_mobile_otp_url,
            {"phone": self.phone, "otp": mobile_otp},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.is_mobile_verified)

    def test_resend_otp_email_and_mobile(self):
        # Create user
        user = User.objects.create(
            first_name='Resend',
            last_name='Test',
            email='resend@example.com',
            phone='9876543210',
            password='irrelevant',
        )
        # Resend email OTP
        url = reverse('auth:resend-otp')
        response = self.client.post(url, {'type': 'email', 'email': user.email}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('resent', response.json()['message'].lower())
        from apps.authentication.models import UserVerifications
        email_otp = UserVerifications.objects.filter(user=user, type='email').latest('created_at')
        self.assertFalse(email_otp.is_used)
        # Resend mobile OTP
        response = self.client.post(url, {'type': 'mobile', 'phone': user.phone}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('resent', response.json()['message'].lower())
        mobile_otp = UserVerifications.objects.filter(user=user, type='mobile').latest('created_at')
        self.assertFalse(mobile_otp.is_used)
