from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.gst.constants import (
    ERROR_MISSING_GSTIN,
    ERROR_PENDING_AUTHENTICATION,
    EXCEPTION_NOTIFICATION
)
from apps.gst.models import Notifications, TimeRange
from apps.authentication.models import UserGstInfo
from apps.gst.permissions import IsActiveGSTSubscriber
from apps.gst.serializers import NotificationSerializer


class NotificationsList(APIView):
    permission_classes = [IsAuthenticated] 

    def get(self, request):
        """
        Retrieves a list of notifications for the authenticated user.

        This endpoint fetches all notifications associated with the user's GST information.
        It returns a paginated list of notifications, including details such as title, message,
        and read status.

        Permissions:
            - User must be authenticated (`IsAuthenticated`).
            - User must be an active GST subscriber (`IsActiveGSTSubscriber`).

        Responses:
            - 200 OK: Returns a paginated list of notifications.
            - 404 NOT FOUND: If no notifications are found for the user.
            - 400 BAD REQUEST: If an error occurs while fetching notifications.
        """
        user = request.user

        try:
            notifications = Notifications.objects.filter(user=user).order_by('-created_at')
            if not notifications.exists():
                return Response({"message": "No notifications found."}, status=status.HTTP_404_NOT_FOUND)

            serializer = NotificationSerializer(notifications, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"message": f"Error fetching notifications: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

class NotificationMarkRead(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        """
        Marks notifications as read for the authenticated user.

        This endpoint allows the user to mark one or more notifications as read.
        It expects a list of notification IDs in the request body.

        Permissions:
            - User must be authenticated (`IsAuthenticated`).
            - User must be an active GST subscriber (`IsActiveGSTSubscriber`).

        Request Body:
            - `notification_ids` (list of int): A list of notification IDs to mark as read.
            - `mark_all` (bool): Optional. If True, marks all notifications for the user as read.

        Responses:
            - 200 OK: If the notifications were successfully marked as read.
            - 400 BAD REQUEST: If no notification IDs are provided or if an error occurs.
            - 404 NOT FOUND: If no notifications match the provided IDs.
        """
        user = request.user
        mark_all = request.data.get("mark_all", False)
        notification_ids = request.data.get("notification_ids", [])

        

        try:
            if mark_all:
                notifications = Notifications.objects.filter(user=user)
                if not notifications.exists():
                    return Response({"message": "No notifications found for user."}, status=status.HTTP_404_NOT_FOUND)
            else:
                if not notification_ids or not isinstance(notification_ids, list):
                    return Response({"message": "No valid notification IDs provided."}, status=status.HTTP_400_BAD_REQUEST)
                notifications = Notifications.objects.filter(id__in=notification_ids, user=user)
                if not notifications.exists():
                    return Response({"message": "No matching notifications found."}, status=status.HTTP_404_NOT_FOUND)

            notifications.update(read=True)
            return Response({"message": "Notifications marked as read."}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"message": f"Error marking notifications as read: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)


