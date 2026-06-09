import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

# Import the utility function to get the group name
from .utils import get_user_group_name 

User = get_user_model() # Get the currently active User model

class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time user notifications.
    Handles connection, disconnection, and sending messages to a user's specific group.
    """

    async def connect(self):
        """
        Called when the WebSocket handshaking is complete and the connection is open.
        Authenticates the user and adds them to their unique notification group.
        """
        # Ensure the user is authenticated.
        # self.scope["user"] is populated by AuthMiddlewareStack in your asgi.py
        self.user = self.scope["user"] 
        
        if not self.user.is_authenticated:
            # Reject the connection if the user is not authenticated
            await self.close()
            print("WebSocket connection rejected: User not authenticated.")
            return

        # Determine the user's unique group name
        self.user_group_name = get_user_group_name(self.user.id)

        # Add the consumer's channel to the user's notification group
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )

        # Accept the WebSocket connection
        await self.accept()
        print(f"WebSocket connected: User ID {self.user.id} joined group '{self.user_group_name}'")

    async def disconnect(self, close_code):
        """
        Called when the WebSocket closes for any reason.
        Removes the consumer's channel from the user's notification group.
        """
        if self.user and self.user.is_authenticated:
            # Leave user-specific group
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )
            print(f"WebSocket disconnected: User ID {self.user.id} left group '{self.user_group_name}' (Close Code: {close_code})")
        else:
            print(f"WebSocket disconnected: Unauthenticated user (Close Code: {close_code})")

    async def receive(self, text_data):
        """
        Called when a message is received from the WebSocket.
        This consumer is primarily for server-to-client notifications,
        so incoming messages are not expected for core functionality.
        If the frontend needs to send commands (e.g., mark as read),
        this method would be extended.
        """
        print(f"Received message from WebSocket (User ID {self.user.id}): {text_data}")
        # Example: if you wanted to echo messages back:
        # await self.send(text_data=json.dumps({"message": "Message received!"}))

    async def new_notification_message(self, event):
        """
        Handles messages sent to the 'new_notification_message' type by the channel layer.
        This method is called when `send_websocket_notification_sync` pushes a message
        to this consumer's group.
        """
        notification_payload = event["message"]
        
        # Send the JSON payload directly to the connected WebSocket
        await self.send(text_data=json.dumps(notification_payload))
        print(f"Sent notification via WebSocket to User ID {self.user.id}: {notification_payload['data']['title']}")