from django.db import transaction
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.gst.models import User, UserGstInfo, Notifications


def get_user_group_name(user_id):
    """
    Generates a unique group name for a specific user.
    This group will receive all notifications for that user.
    Frontend consumers connect to this group.
    """
    return f"user_{user_id}_notifications"

# You can keep this for future use or remove if not needed for GSTIN-specific broadcasts
def get_gstin_group_name(gstin):
    """
    Generates a unique group name for a specific GSTIN.
    This group can be used for GSTIN-specific broadcasts if needed.
    """
    return f"gstin_{gstin}_notifications"


def _send_websocket_message_async(group_name: str, payload: dict):
    """
    INTERNAL ASYNC HELPER:
    Asynchronously sends a message to a Channels group.
    This function is intended to be called by async_to_sync from a synchronous context.
    """
    channel_layer = get_channel_layer()
    if not channel_layer:
        print("Error: Channel layer not configured. Cannot send WebSocket notification.")
        return

    try:
        # The 'type' key in the message dictionary maps to a method in your consumer
        # (e.g., if type is 'new_notification_message', consumer should have a method 'new_notification_message(self, event)')
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "new_notification_message", # This name MUST match a method in your NotificationConsumer
                "message": payload,
            }
        )
        print(f"Sent WebSocket notification to group '{group_name}'. Notification ID: {payload['data'].get('id', 'N/A')}")
    except Exception as e:
        print(f"Error sending WebSocket notification to group {group_name}: {e}")


def send_websocket_notification_sync(
    user_id: int,
    module: str,
    title: str,
    message: str,
    notification_type: str = "info",
    metadata: dict = None,
    user_gst_info_id: int = None,
):
    """
    Saves a notification to the database and sends a real-time WebSocket notification.
    This function is designed to be called from synchronous contexts (e.g., Django-Q tasks).

    Args:
        user_id (int): The ID of the user to notify.
        module (str): The module associated with the notification (e.g., "reconciliation", "data_2b_fetch").
        title (str): A concise title for the notification.
        message (str): The main content or detailed message of the notification.
        notification_type (str, optional): Type/severity of the notification ("success", "error", "info", "warning"). Defaults to "info".
        user_gst_info_id (int, optional): The ID of the UserGstInfo object if the notification is GSTIN-specific.
        metadata (dict, optional): Additional key-value pairs related to the notification (e.g., financial_year, status, record_count). Defaults to None.
        action_type (str, optional): Type of action for the frontend (e.g., "view_details"). Defaults to "view_details".
        action_label (str, optional): Label for the action button. Defaults to "View Details".
        action_url (str, optional): URL to navigate to when the action is performed. Defaults to "/gst/reconciliation/overview".
        action_app (str, optional): App context for the action. Defaults to "gst".
        thread_id (str, optional): Identifier to group related notifications. Defaults to None.
    """
    
    try:
        with transaction.atomic():
            user = User.objects.get(id=user_id)
            user_gst_info = None
            if user_gst_info_id:
                user_gst_info = UserGstInfo.objects.get(id=user_gst_info_id)
            
            notification = Notifications.objects.create(
                user=user,
                user_gst_info=user_gst_info, 
                module=module,
                title=title,
                message=message,
                type=notification_type,
                priority="normal", 
                metadata=metadata if metadata is not None else {},
                read=False,
                expires_at=None,
                thread_id="0",
                
                action_type="",
                action_label="",
                action_url="",
                action_app="",
            )
            
            # Get the formatted payload from the newly created notification instance
            notification_payload = notification.to_websocket_format()

        # After successfully saving, send the WebSocket message
        group_name = get_user_group_name(user_id)
        
        # Call the internal async helper via async_to_sync
        _send_websocket_message_async(group_name, notification_payload)

        print(f"Notification (DB ID: {notification.id}) saved and WebSocket message queued.")

    except User.DoesNotExist:
        print(f"Warning: User with ID {user_id} not found for notification. Notification not saved/sent.")
    except UserGstInfo.DoesNotExist:
        print(f"Warning: UserGstInfo with ID {user_gst_info_id} not found for notification. Notification not saved/sent.")
    except Exception as e:
        print(f"Error in send_websocket_notification_sync: {e}")
        
