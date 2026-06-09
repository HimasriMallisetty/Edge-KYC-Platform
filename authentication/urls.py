from django.urls import path
from .views import (
    CompanyDetailView,
    GoogleLoginApiView,
    LoginAPIView,
    SignupAPIView,
    RequestPasswordResetAPI,
    VerifyResetLinkAPI,
    ResetPasswordAPI,
    GstGenerateOtpAPIView,
    GstRefreshOtpAPIView,
    GstTerminateSessionAPIView,
    GstVerifyOtpAPIView,
    VerifyEmailOtpAPIView,
    VerifyMobileOtpAPIView,
    ResendOtpAPIView,
)


app_name = "auth"

urlpatterns = [
    path("login/", LoginAPIView.as_view(), name="login"),
    path("login/google/", GoogleLoginApiView.as_view(), name="google-login"),
    path("signup/", SignupAPIView.as_view(), name="signup"),
    path("company/", CompanyDetailView.as_view(), name="company"),
    path("request-reset/", RequestPasswordResetAPI.as_view(), name="request-reset"),
    path("verify-code/", VerifyResetLinkAPI.as_view(), name="verify-reset"),
    path("reset-password/", ResetPasswordAPI.as_view(), name="reset-password"),
    path("gst/otp/generate", GstGenerateOtpAPIView.as_view(), name="gst-otp-generate"),
    path("gst/otp/verify", GstVerifyOtpAPIView.as_view(), name="gst-otp-verify"),
    path("gst/token/refresh", GstRefreshOtpAPIView.as_view(), name="gst-token-refresh"),
    path(
        "gst/session/terminate",
        GstTerminateSessionAPIView.as_view(),
        name="gst-token-terminate",
    ),
    path("verify-email-otp/", VerifyEmailOtpAPIView.as_view(), name="verify-email-otp"),
    path("verify-mobile-otp/", VerifyMobileOtpAPIView.as_view(), name="verify-mobile-otp"),
    path("resend-otp/", ResendOtpAPIView.as_view(), name="resend-otp"),
]
