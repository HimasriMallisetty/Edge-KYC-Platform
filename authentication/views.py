import hashlib
import random
from datetime import timedelta
from django.contrib.auth.hashers import check_password
from django.utils.timezone import now
from django.template import loader
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from apps.core.sandbox import SandboxClient
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from firebase_admin import auth as firebase_auth

from .firebase import *
from .models import Company, PasswordReset, User, UserGstInfo, UserVerifications
from .serializers import UserSignupSerializer, UserSerializer
from ..payment.models import Credits
from .constants import PASSWORD_RESET_EMAIL
from .utils import send_otp_to_email, send_otp_to_mobile
from apps.gst.utils import insert_time_range_data
from ..core.sandbox import is_jwt_expired


class GoogleLoginApiView(APIView):
    """
    Verify id token with firba

    Path Parameters:
        token (str): id token.

    Returns:
        Response: A Response object containing user details with jwt token.
    """

    def post(self, request, *args, **kwargs):
        token = request.data.get("token")
        try:
            decoded_token = firebase_auth.verify_id_token(token)

            uid = decoded_token["uid"]
            email = decoded_token.get("email", "")
            picture = decoded_token.get("picture", "")

            splited_name = decoded_token.get("name", "").split(" ")
            first_name = splited_name[0]
            last_name = splited_name[-1]

            user, created = User.objects.update_or_create(
                email=email,
                defaults={
                    "uid": uid,
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "image_path": picture,
                    "is_email_verified": True,
                },
            )

            if created:
                Credits.objects.create(user=user, total=300)

            # Refetch user with roles prefetched
            user = User.objects.prefetch_related("roles").get(pk=user.pk)

            user_data = {
                "id": user.pk,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "is_email_verified": user.is_email_verified,
                "is_mobile_verified": user.is_mobile_verified,
                "picture": user.image_path,
                "token": user.get_token(),
                "is_admin": user.is_superuser,
                "roles": list(user.roles.values_list("name", flat=True)),
            }

            return Response(user_data)
        except Exception as e:
            return Response({"error": str(e)}, status=401)


class CompanyDetailView(RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = UserSerializer

    def get_object(self):
        return User.objects.select_related("company").get(id=self.request.user.id)

    def update(self, request, *args, **kwargs):
        company, _ = Company.objects.update_or_create(
            email=request.data.get("company_email"),
            defaults={
                "name": request.data.get("company_name"),
                "phone": request.data.get("company_phone"),
                "email": request.data.get("company_email"),
                "address": request.data.get("company_address"),
            },
        )

        user = self.get_object()
        name_parts = request.data.get("name", "").strip().split(" ")
        first_name = " ".join(name_parts[:-1]) if len(name_parts) > 1 else name_parts[0]
        last_name = name_parts[-1] if len(name_parts) > 1 else ""
        user.first_name = first_name
        user.last_name = last_name
        user.phone = request.data.get("phone", "")
        user.company = company
        user.save()

        serializer = UserSerializer(user)

        return Response(serializer.data)


class SignupAPIView(CreateAPIView):
    serializer_class = UserSignupSerializer
    queryset = User.objects.filter(is_active=True)


class LoginAPIView(APIView):
    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        password = request.data.get("password")

        if not email or not password:
            return Response(
                {"error": "Email and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.prefetch_related("roles").get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error": {"email": "User does not exist."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user.password or not check_password(password, user.password):
            return Response(
                {"error": {"password": "Invalid password."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Construct the response data
        response_data = {
            "id": user.pk,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "picture": getattr(user, "image_path", None),
            "is_email_verified": user.is_email_verified,
            "is_mobile_verified": user.is_mobile_verified,
            "token": user.get_token(),
            "is_admin": user.is_superuser,
            "roles": list(user.roles.values_list("name", flat=True)),
        }

        return Response(response_data, status=status.HTTP_200_OK)


class RequestPasswordResetAPI(APIView):
    html_template = PASSWORD_RESET_EMAIL

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response(
                {"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.filter(email=email).first()
        if not user:
            return Response(
                {"error": "User with this email does not exist"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Generate unique code
        unique_string = f"{user.id}-{random.randint(1000, 9999)}"
        code = hashlib.md5(unique_string.encode()).hexdigest()

        PasswordReset.objects.create(user=user, code=code)

        # Reset link
        reset_link = (
            f"{settings.STATIC_APP_URL}/reset-password?userId={user.id}&code={code}"
        )

        # Context data for the template
        context_data = {
            "first_name": user.first_name,
            "reset_link": reset_link,
        }

        # Load and render the HTML template
        template = loader.get_template(self.html_template)
        html_email_body = template.render(context_data)

        email_message = EmailMultiAlternatives(
            subject="Reset Your Password",
            body="Please reset your password using the provided link.",  # Fallback plain-text content
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        email_message.attach_alternative(html_email_body, "text/html")
        email_message.send()

        return Response(
            {"message": "Password reset link sent to email"}, status=status.HTTP_200_OK
        )


class VerifyResetLinkAPI(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        user_id = request.query_params.get("userId")
        code = request.query_params.get("code")

        if not user_id or not code:
            return Response(
                {"error": "Missing userId or code"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            password_reset = PasswordReset.objects.get(
                user_id=user_id, code=code, is_used=False
            )
            if password_reset.created_at + timedelta(minutes=15) < now():
                return Response(
                    {"error": "Reset link expired"}, status=status.HTTP_400_BAD_REQUEST
                )

            # Generate JWT token
            user = password_reset.user
            token = user.get_token()
            return Response({"token": token}, status=status.HTTP_200_OK)

        except PasswordReset.DoesNotExist:
            return Response(
                {"error": "Invalid or expired reset link"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class ResetPasswordAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")

        if not new_password or not confirm_password:
            return Response(
                {"error": "Both fields are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_password != confirm_password:
            return Response(
                {"error": "Passwords do not match"}, status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user
        user.set_password(new_password)
        user.save()

        return Response(
            {"message": "Password updated successfully"}, status=status.HTTP_200_OK
        )


class GstGenerateOtpAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request):
        username = request.data.get("username")
        gstin = request.data.get("gstin")
        # Construct the response data
        try:
            sandbox_client = SandboxClient()

            gst_info = (
                UserGstInfo.objects.filter(
                    user=request.user, gstin=gstin, gst_username=username
                )
                .order_by("-refreshed_at")
                .first()
            )

            # Avoid Duplicate Authentication
            if gst_info:
                user_token = gst_info.gst_token
                if not is_jwt_expired(user_token):
                    user_gst_information = {
                        "username": gst_info.gst_username,
                        "gstin": gst_info.gstin,
                        "company_name": gst_info.company_name,
                    }
                    return Response(
                        {
                            "message": "GSTIN authentication is already done.",
                            "data": user_gst_information,
                        },
                        status=status.HTTP_200_OK,
                    )

            response = sandbox_client._generate_gst_otp(username=username, gstin=gstin)

            if response["data"]["status_cd"] == "1":
                return Response("OTP Generated Successfully", status=status.HTTP_200_OK)

            return Response(response["data"]["error"]["message"], status=403)
        except Exception as e:
            return Response({"error": str(e)}, status=401)


class GstVerifyOtpAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request):
        user = request.user
        username = request.data.get("username")
        gstin = request.data.get("gstin")
        company_name = request.data.get("company_name")

        otp = request.query_params.get("otp")
        # Construct the response data
        try:
            sandbox_client = SandboxClient()
            response = sandbox_client._verify_gst_otp(
                username=username, gstin=gstin, otp=otp
            )

            if response["data"]["status_cd"] == "1":
                gst_token = response["data"]["access_token"]
                auth_status = UserGstInfo.objects.filter(
                    user=user, gstin=gstin, gst_username=username
                ).exists()

                if auth_status:
                    UserGstInfo.objects.filter(
                        user=user,
                        gst_username=username,
                        gstin=gstin,
                        company_name=company_name,
                    ).update(gst_token=gst_token)

                    gst_info = (
                        UserGstInfo.objects.filter(
                            user=user, gstin=gstin, gst_username=username
                        )
                        .order_by("-refreshed_at")
                        .first()
                    )

                else:
                    UserGstInfo.objects.create(
                        user=user,
                        gst_token=gst_token,
                        gst_username=username,
                        gstin=gstin,
                        company_name=company_name,
                    )

                    gst_info = (
                        UserGstInfo.objects.filter(
                            user=user, gstin=gstin, gst_username=username
                        )
                        .order_by("-refreshed_at")
                        .first()
                    )
                    insert_time_range_data(user, gst_info)

                user_gst_information = {
                    "username": gst_info.gst_username,
                    "gstin": gst_info.gstin,
                    "company_name": gst_info.company_name,
                }

                return Response(
                    {
                        "data": user_gst_information,
                        "message": "Authorization Successful",
                    },
                    status=status.HTTP_200_OK,
                )

            return Response(
                response["data"]["error"]["message"], status=status.HTTP_403_FORBIDDEN
            )

        except Exception as e:
            print(e)
            return Response({"error": str(e)}, status=401)


class GstRefreshOtpAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request):
        user = request.user
        username = request.data.get("username")
        gstin = request.data.get("gstin")
        # Construct the response data
        try:
            user_gst_info = UserGstInfo.objects.filter(
                user=user, gst_username=username, gstin=gstin
            ).first()
            if user_gst_info:
                sandbox_client = SandboxClient()
                response = sandbox_client._refresh_gst_jwt(
                    token=user_gst_info.gst_token
                )

                if response["data"]["status_cd"] == "1":
                    gst_token = response["data"]["access_token"]
                    UserGstInfo.objects.update_or_create(
                        user=user,
                        gst_username=username,
                        gstin=gstin,
                        defaults={"gst_token": gst_token},
                    )

                    return Response(
                        "Authorization Successful", status=status.HTTP_200_OK
                    )
            else:
                return Response("Error refreshing OTP", status=403)

            return Response("No GST Token found for this user.", status=404)

        except Exception as e:
            print(e)
            return Response({"error": str(e)}, status=401)


class GstTerminateSessionAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request):
        user = request.user
        username = request.data.get("username")
        gstin = request.data.get("gstin")
        # Construct the response data
        try:
            user_gst_info = UserGstInfo.objects.filter(
                user=user, gst_username=username, gstin=gstin
            ).first()
            if user_gst_info:
                sandbox_client = SandboxClient()
                response = sandbox_client._terminate_gst_session(
                    token=user_gst_info.gst_token
                )
                if response["data"]["status_cd"] == "1":
                    UserGstInfo.objects.update_or_create(
                        user=user,
                        gst_username=username,
                        gstin=gstin,
                        defaults={"gst_token": ""},
                    )

                    return Response("Session Terminated", status=status.HTTP_200_OK)
            else:
                return Response("Error terminating session", status=403)

            return Response("No GST Token found for this user.", status=404)

        except Exception as e:
            print(e)
            return Response({"error": str(e)}, status=401)


class VerifyEmailOtpAPIView(APIView):
    def post(self, request):
        email = request.data.get("email")
        otp = request.data.get("otp")
        user = User.objects.filter(email=email).first()
        if not user:
            return Response({"error": "User not found."}, status=404)

        otp_obj = UserVerifications.objects.filter(
            user=user, type="email", otp=otp, is_used=False
        ).first()
        if not otp_obj or otp_obj.expiry < now():
            return Response({"error": "Invalid or expired OTP."}, status=400)
        otp_obj.is_used = True
        otp_obj.save()
        user.is_email_verified = True
        user.save()
        return Response({"message": "Email verified successfully."})


class VerifyMobileOtpAPIView(APIView):
    def post(self, request):
        phone = request.data.get("phone")
        otp = request.data.get("otp")
        user = User.objects.filter(phone=phone).first()
        if not user:
            return Response({"error": "User not found."}, status=404)

        otp_obj = UserVerifications.objects.filter(
            user=user, type="mobile", otp=otp, is_used=False
        ).first()
        if not otp_obj or otp_obj.expiry < now():
            return Response({"error": "Invalid or expired OTP."}, status=400)
        otp_obj.is_used = True
        otp_obj.save()
        user.is_mobile_verified = True
        user.save()

        return Response({"message": "Mobile verified successfully."})


class ResendOtpAPIView(APIView):
    def post(self, request):
        otp_type = request.data.get("type")
        if otp_type == "email":
            email = request.data.get("email")
            user = User.objects.filter(email=email).first()
            if not user:
                return Response({"error": "User not found."}, status=404)
            send_otp_to_email(user)

            return Response({"message": "Email OTP resent successfully."})
        elif otp_type == "mobile":
            phone = request.data.get("phone")
            user = User.objects.filter(phone=phone).first()
            if not user:
                return Response({"error": "User not found."}, status=404)
            send_otp_to_mobile(user)

            return Response({"message": "Mobile OTP resent successfully."})
        else:
            return Response(
                {"error": "Invalid type. Must be 'email' or 'mobile'."}, status=400
            )
