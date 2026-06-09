from .models import User, UserGstInfo
from rest_framework import serializers
from django.contrib.auth.hashers import make_password, check_password
from rest_framework.exceptions import ValidationError
from ..payment.models import Credits


class UserSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    company_phone = serializers.CharField(source="company.phone", read_only=True)
    company_email = serializers.CharField(source="company.email", read_only=True)
    company_address = serializers.CharField(source="company.address", read_only=True)
    is_email_verified = serializers.BooleanField(read_only=True)
    is_mobile_verified = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "phone",
            "email",
            "company_name",
            "company_phone",
            "company_email",
            "company_address",
            "is_email_verified",
            "is_mobile_verified",
        ]


class UserSignupSerializer(serializers.ModelSerializer):
    name = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, min_length=6)
    confirmPassword = serializers.CharField(write_only=True)
    phone = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "name",
            "first_name",
            "last_name",
            "phone",
            "email",
            "password",
            "confirmPassword",
        ]

    def validate(self, data):
        # Ensure passwords match
        if data["password"] != data["confirmPassword"]:
            raise ValidationError({"password": "Passwords do not match."})

        # Ensure email is unique
        if User.objects.filter(email=data["email"].lower()).exists():
            raise ValidationError({"email": "Email already exists."})

        return data

    def create(self, validated_data):
        # Split the name into first and last names
        name = validated_data.pop("name").split()
        first_name = name[0] if len(name) > 0 else ""
        last_name = " ".join(name[1:]) if len(name) > 1 else ""

        # Remove confirm_password from validated_data
        validated_data.pop("confirmPassword", None)

        # Create the user instance
        user = User.objects.create(
            first_name=first_name,
            last_name=last_name,
            email=validated_data["email"].lower(),
            phone=validated_data.get("phone", ""),
            password=make_password(validated_data["password"]),
        )

        Credits.objects.create(
            user=user, total=100
        )  # You can modify the default total as needed
        # Send OTPs
        from .utils import send_otp_to_email, send_otp_to_mobile

        send_otp_to_email(user)
        send_otp_to_mobile(user)
        return user


class UserGstInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserGstInfo
        fields = ["gst_token", "refreshed_at", "gstin", "gst_username"]
