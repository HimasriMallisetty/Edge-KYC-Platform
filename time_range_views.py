from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated


from apps.gst.constants import (
    ERROR_MISSING_GSTIN,
    ERROR_MISSING_USERNAME,
    EXCEPTION_TIMERANGE,
    ERROR_PENDING_AUTHENTICATION
)
from apps.gst.models import TimeRange
from apps.authentication.models import UserGstInfo
from apps.gst.serializers import TimeRangeSerializer

class TimeRangeAPI(APIView):
    """
    API endpoint to retrieve time range data for a specific GSTIN and username.
    Requires user to be authenticated.

    Request Body:
    - gstin (str): GST Identification Number.
    - username (str): GST portal username.

    Returns:
    - 200 OK: Time range data successfully retrieved.
    - 404 NOT FOUND: If GSTIN or username is missing, or no matching GST info is found.
    - 400 BAD REQUEST: If an error occurs while fetching time range data.

    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        request_body_gstin = request.data.get("gstin")
        request_body_username = request.data.get("username")

        if request_body_gstin is None:
            return Response(
                {"message": ERROR_MISSING_GSTIN}, status=status.HTTP_404_NOT_FOUND
            )

        if request_body_username is None:
            return Response(
                {"message": ERROR_MISSING_USERNAME}, status=status.HTTP_404_NOT_FOUND
            )

        gst_info = (
            UserGstInfo.objects.filter(
                user=user, gstin=request_body_gstin, gst_username=request_body_username
            )
            .order_by("-refreshed_at")
            .first()
        )

        if not gst_info:
            return Response(
                {"message": ERROR_PENDING_AUTHENTICATION},
                status=status.HTTP_404_NOT_FOUND,
            )
        gst_info_id = gst_info.id

        try:
            time_range_data = TimeRange.objects.filter(
                user=request.user, user_gst_info_id=gst_info_id
            ).order_by("-id")
            serializer = TimeRangeSerializer(time_range_data, many=True)

            return Response(serializer.data, status=status.HTTP_200_OK)
        except:
            return Response(
                {"message": EXCEPTION_TIMERANGE}, status=status.HTTP_400_BAD_REQUEST
            )
