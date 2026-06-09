from django.utils.translation import gettext_lazy as _

JWT_EXPIRY_TIME = 24
ADDRESS_ERR_MSG = "Invalid Address. At least 2 words are required."
USER_NAME_ERR_MSG = (
    "'{}' contains invalid characters. Allowed characters "
    "are A-Za-z ,.'- and must start with alphabet."
)
OTHER_NAME_ERR_MSG = (
    "'{}' contains invalid characters. Allowed characters "
    "are A-Za-z0-9 ,.'-/\"&`%$():_ "
    "and must start with alphanumeric."
)
PHONE_NUMBER_ERR_MSG = "Invalid phone number."
PASSWORD_RESET_EMAIL = "password_reset.html"

OTP_TYPE_CHOICES = (
    ("email", "Email"),
    ("mobile", "Mobile"),
)


class Roles:
    SUPERADMIN = "SuperAdmin"
    ADMIN = "Admin"
    MAKER = "Maker"
    CHECKER = "Checker"
    APPROVER = "Approver"

    CHOICES = [
        (SUPERADMIN, _("SuperAdmin")),
        (ADMIN, _("Admin")),
        (MAKER, _("Maker")),
        (CHECKER, _("Checker")),
        (APPROVER, _("Approver")),
    ]
