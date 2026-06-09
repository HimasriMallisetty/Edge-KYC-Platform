import jwt
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _
from ..core.models import CoreModel
from .constants import JWT_EXPIRY_TIME, OTP_TYPE_CHOICES, Roles
from .managers import UserManager
from .validators import (
    name_validator,
    user_name_validator,
    phone_validator,
    address_validator,
)


class Company(CoreModel):
    name = models.CharField(max_length=150, validators=[name_validator])
    phone = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        default="",
        validators=[phone_validator],
        help_text=_("Please provide plain text phone number. e.g:3102345678"),
    )
    email = models.EmailField(db_index=True, unique=True, null=True)
    address = models.CharField(
        max_length=300,
        validators=[address_validator],
        help_text=_("Please provide at least 2 words."),
        blank=True,
        null=True,
    )

    def clean(self):
        if self.email is not None:
            self.email = self.email.lower()

        return super(User, self).clean()

    def __str__(self):
        return "{0}".format(self.name)

    def __repr__(self):
        return "<Company: {0}>".format(self.name)

    class Meta:
        db_table = "company"
        verbose_name = "Company"


class Role(CoreModel):
    name = models.CharField(max_length=32, choices=Roles.CHOICES, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "role"
        verbose_name = "Role"
        verbose_name_plural = "Roles"


class User(AbstractBaseUser, PermissionsMixin, CoreModel):
    first_name = models.CharField(
        max_length=50, blank=True, null=True, validators=[user_name_validator]
    )
    last_name = models.CharField(
        max_length=50, blank=True, null=True, validators=[user_name_validator]
    )
    email = models.EmailField(db_index=True, unique=True)
    password = models.CharField(max_length=128, blank=True, null=True)
    phone = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        default="",
        validators=[phone_validator],
        help_text=_("Please provide plain text phone number. e.g:3102345678"),
    )
    birth_date = models.DateField(blank=True, null=True)
    image_path = models.CharField(max_length=512, null=True, blank=True)
    address = models.CharField(
        max_length=300,
        validators=[address_validator],
        help_text=_("Please provide at least 2 words."),
        blank=True,
        null=True,
    )
    uid = models.CharField(max_length=255, blank=True, null=True)
    company = models.ForeignKey(
        Company, related_name="users", blank=True, null=True, on_delete=models.CASCADE
    )
    is_email_verified = models.BooleanField(default=False)
    is_mobile_verified = models.BooleanField(default=False)
    roles = models.ManyToManyField(
        Role,
        related_name="users",
        db_table="user_roles",
        blank=True,
    )

    USERNAME_FIELD = "email"
    objects = UserManager()

    def clean(self):
        if self.email is not None:
            self.email = self.email.lower()

        return super(User, self).clean()

    @property
    def is_staff(self):
        return self.is_superuser

    def get_short_name(self):
        return self.first_name

    def get_full_name(self):
        full_name = "%s %s" % (self.first_name, self.last_name)

        return full_name

    @property
    def company_name(self):
        return self.company.name if self.company else ""

    def get_token(self, max_expiry_time=JWT_EXPIRY_TIME):
        return self._generate_jwt_token(max_expiry_time)

    def _generate_jwt_token(self, max_expiry_time):
        dt = datetime.now() + timedelta(hours=max_expiry_time)

        roles = list(self.roles.values_list("name", flat=True))

        token = jwt.encode(
            {
                "id": self.pk,
                "name": self.get_full_name(),
                "email": self.email,
                "exp": int(dt.timestamp()),
                "is_admin": self.is_superuser,
                "company_name": self.company_name,
                "is_email_verified": self.is_email_verified,
                "is_mobile_verified": self.is_mobile_verified,
                "roles": roles,
            },
            settings.SECRET_KEY,
            algorithm="HS256",
        )

        return token

    def __str__(self):
        return "{0}".format(self.get_full_name())

    def __repr__(self):
        return "<User: {0}>".format(self.get_full_name())

    class Meta:
        db_table = "user"
        verbose_name = "User"
        ordering = ("first_name", "last_name")
        indexes = [
            models.Index(
                fields=[
                    "-is_active",
                ]
            ),
        ]


class PasswordReset(CoreModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=255, unique=True)
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"Password reset for {self.user.email} - {self.code}"


class UserGstInfo(CoreModel):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="gst_tokens", null=True
    )
    gst_username = models.CharField(max_length=500, default="default_value")
    gstin = models.CharField(max_length=500, default="default_value")
    gst_token = models.TextField()
    refreshed_at = models.DateTimeField(auto_now=True)
    company_name = models.CharField(max_length=500, default="default_value")


class UserVerifications(CoreModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="otps")
    otp = models.CharField(max_length=6)
    type = models.CharField(max_length=10, choices=OTP_TYPE_CHOICES)
    is_used = models.BooleanField(default=False)
    expiry = models.DateTimeField()

    def __str__(self):
        return f"{self.user.email} - {self.type} OTP: {self.otp}"

    class Meta:
        db_table = "user_verification"
        verbose_name = "User Verification"
