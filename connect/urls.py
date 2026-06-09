# from django.urls import path
# from .views import EmailReplyCreateView

# urlpatterns = [
#     path("email-reply/", EmailReplyCreateView.as_view(), name="email-reply-create"),
# ]

from django.urls import path
from .views import (
    EmailReplyProcessView, 
    SendEmailView, 
    ThreadListView, 
    ThreadDetailView
)

urlpatterns = [
    # Updated endpoint for processing incoming email replies (unified with Email model)
    path("email-reply/", EmailReplyProcessView.as_view(), name="email-reply-process"),
    
    # New endpoints for sending emails and managing threads
    path("send-email/", SendEmailView.as_view(), name="send-email"),
    path("threads/", ThreadListView.as_view(), name="thread-list"),
    path("threads/<int:thread_id>/", ThreadDetailView.as_view(), name="thread-detail"),
]