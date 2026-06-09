from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.authentication.models import UserGstInfo
from apps.gst.constants import (
    MESSAGE_USER_AUTH_DONE,
    MESSAGE_USER_AUTH_PENDING,
    EXCEPTION_USER_AUTH_DETAILS
)


class UserAuthDetails(APIView):
    """
    API endpoint to retrieve the authenticated user's GST authorization info.

    Returns:
    - 200 OK: If GST info is found or not found.
    - 400 BAD REQUEST: On unexpected error.

    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            user_gst_info = (
                UserGstInfo.objects.filter(
                    user=user,
                )
                .order_by("-refreshed_at")
                .first()
            )

            if user_gst_info is None:
                return Response(
                    {"message": MESSAGE_USER_AUTH_PENDING, "data": None},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {
                        "message": MESSAGE_USER_AUTH_DONE,
                        "data": {
                            "username": user_gst_info.gst_username,
                            "gstin": user_gst_info.gstin,
                            "company_name": user_gst_info.company_name,
                        },
                    },
                    status=status.HTTP_200_OK,
                )
        except:
            return Response(
                {"message": EXCEPTION_USER_AUTH_DETAILS},
                status=status.HTTP_400_BAD_REQUEST,
            )
