from rest_framework import serializers
from .models import EmailAttachment, Thread, Email


class EmailAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailAttachment
        fields = [
            "id",
            "filename",
            "file",
            "file_url",
            "file_size",
            "attachment_type",
            "created_at",
        ]


class ThreadSerializer(serializers.ModelSerializer):
    first_email_message_id = serializers.CharField(
        source="first_email.message_id", read_only=True
    )

    class Meta:
        model = Thread
        fields = [
            "id",
            "subject",
            "first_email",
            "first_email_message_id",
            "to_email",
            "cc_email",
            "bcc_email",
            "reminder_enabled",
            "reminder_frequency_days",
            "reminder_count",
            "stop_reminders_after",
            "vendor_name",
            "supplier_name",
            "vendor_gstin",
            "invoice_count",
            "created_at",
            "updated_at",
        ]


class EmailSerializer(serializers.ModelSerializer):
    attachments = EmailAttachmentSerializer(many=True, read_only=True)

    # date = serializers.DateTimeField(required=False, allow_null=True)
    class Meta:
        model = Email
        fields = [
            "id",
            "message_id",
            "thread",
            "reply_to",
            "from_email",
            "to_email",
            "cc_email",
            "bcc_email",
            "subject",
            "in_reply_to",
            "references",
            "content_plain",
            "content_html",
            "reply_message",
            "raw_body",
            "email_type",
            "date",
            "created_at",
            "attachments",
        ]


class SendEmailSerializer(serializers.Serializer):
    # Thread fields
    to_email = serializers.EmailField()
    cc_email = serializers.CharField(required=False, allow_blank=True)
    bcc_email = serializers.CharField(required=False, allow_blank=True)
    # subject = serializers.CharField(max_length=255)
    subject = serializers.CharField(
        required=False, allow_blank=True, default="No Subject"
    )
    supplier_name = serializers.CharField(required=False, allow_blank=True)

    # Email content
    content_plain = serializers.CharField()
    content_html = serializers.CharField(required=False, allow_blank=True)

    # Threading
    reply_to_message_id = serializers.CharField(required=False, allow_blank=True)

    # Thread settings
    reminder_enabled = serializers.BooleanField(allow_null=True, required=False)
    reminder_frequency_days = serializers.IntegerField(allow_null=True, required=False)
    reminder_count = serializers.IntegerField(allow_null=True, required=False)
    stop_reminders_after = serializers.CharField(allow_null=True, required=False)

    # Vendor/Invoice info
    vendor_name = serializers.CharField(required=False, allow_blank=True)
    vendor_gstin = serializers.CharField(required=False, allow_blank=True)
    invoice_count = serializers.CharField(required=False, allow_blank=True)
    # Attachments will be handled via request.FILES, so no attachment_path field.

    def validate(self, data):
        # Ensure at least one content field is provided
        if not data.get("content_plain") and not data.get("content_html"):
            raise serializers.ValidationError(
                "Either content_plain or content_html must be provided"
            )

        # If no subject provided, create a default one
        if not data.get("subject"):
            data["subject"] = "No Subject"

        return data


class EmailReplyProcessSerializer(serializers.Serializer):
    """Serializer for processing incoming email replies"""

    raw_body = serializers.CharField()
