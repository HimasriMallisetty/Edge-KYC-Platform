import random
from datetime import timedelta
from django.utils.timezone import now
from django.core.mail import send_mail
from django.conf import settings
from .models import UserVerifications
from apps.core.email import SendEmail

def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp_to_email(user):
    otp = generate_otp()
    expiry = now() + timedelta(minutes=10)
    UserVerifications.objects.create(user=user, otp=otp, type="email", expiry=expiry)
    subject = "Your Email Verification OTP"
    message = f"Your OTP for email verification is: {otp}"
    context_data = {"otp": otp, "user": user}
    html_template = "otp_email.html"
    
    SendEmail(subject, message, [user.email], context_data, html_template, attachment=False)

def send_otp_to_mobile(user):
    otp = generate_otp()
    expiry = now() + timedelta(minutes=10)
    UserVerifications.objects.create(user=user, otp=otp, type="mobile", expiry=expiry)
    # Replace this with actual SMS sending logic
    print(f"Send SMS to {user.phone}: Your OTP is {otp}") 