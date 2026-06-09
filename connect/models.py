from apps.authentication.models import User
from django.db import models
from ..core.models import CoreModel
from .constants import EMAIL_TYPE_CHOICES, ATTACHMENT_TYPE_CHOICES


class Thread(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="connect_threads"
    )
    subject = models.CharField(max_length=255, null=True, blank=True)
    first_email = models.ForeignKey(
        "Email",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="first_email_of_thread",
    )
    to_email = models.EmailField()
    cc_email = models.TextField(blank=True, null=True)
    bcc_email = models.TextField(blank=True, null=True)
    reminder_enabled = models.BooleanField(null=True, blank=True)
    reminder_frequency_days = models.IntegerField(null=True, blank=True)
    reminder_count = models.IntegerField(null=True, blank=True)
    stop_reminders_after = models.CharField(max_length=50, null=True, blank=True)
    vendor_name = models.CharField(max_length=255, blank=True, null=True)
    supplier_name = models.CharField(max_length=255, blank=True, null=True)
    vendor_gstin = models.CharField(max_length=20, blank=True, null=True)
    invoice_count = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Thread {self.id}: {self.subject}"


class Email(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="connect_emails"
    )
    message_id = models.CharField(max_length=255, unique=True)
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="emails")
    reply_to = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL
    )
    from_email = models.EmailField()
    to_email = models.EmailField()
    cc_email = models.TextField(blank=True, null=True)
    bcc_email = models.TextField(blank=True, null=True)
    subject = models.CharField(max_length=255, null=True, blank=True)
    in_reply_to = models.CharField(max_length=255, blank=True, null=True)
    references = models.TextField(blank=True, null=True)
    content_plain = models.TextField(blank=True, null=True)
    content_html = models.TextField(blank=True, null=True)
    reply_message = models.TextField(blank=True, null=True)
    raw_body = models.TextField(blank=True, null=True)
    email_type = models.CharField(
        max_length=10, choices=EMAIL_TYPE_CHOICES, default="sent"
    )
    date = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"Email {self.id}: {self.subject}"


class EmailAttachment(models.Model):

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="connect_attachments"
    )
    email = models.ForeignKey(
        Email, on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(upload_to="attachments/", null=True, blank=True)
    filename = models.CharField(max_length=255, null=True, blank=True)
    file_url = models.URLField(null=True, blank=True)
    file_size = models.CharField(max_length=20, blank=True, null=True)
    attachment_type = models.CharField(
        max_length=20, choices=ATTACHMENT_TYPE_CHOICES, default="USER_UPLOADED"
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"Attachment {self.id}: {self.filename}"


class EmailReminders(CoreModel):
    message_id = models.ForeignKey(
        Email,
        on_delete=models.CASCADE,
        to_field="message_id",  # This specifies that we're linking to the 'message_id' field of Email
        related_name="reminders",
    )
    reminder_enabled = models.BooleanField(default=False)
    reminder_count = models.IntegerField(default=0)
    reminder_status = models.IntegerField(default=0)
    reminders_sent = models.IntegerField(default=0)
    reminders_remaining = models.IntegerField(default=0)
    reminder_enabled = models.BooleanField(default=False)
    next_reminder_date = models.DateField(null=True, blank=True)
    frequency = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"Reminder for {self.message_id.message_id}"
