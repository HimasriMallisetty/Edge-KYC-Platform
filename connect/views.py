import boto3
import os
import tempfile
import base64
import traceback
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import EmailAttachment, Thread, Email, EmailReminders
from .serializers import (
    SendEmailSerializer,
    ThreadSerializer,
    EmailSerializer,
    EmailReplyProcessSerializer,
)
from .email_service import EmailService
from apps.core.s3 import S3Client
from .email_utils import parse_email_payload_complete, clean_message_id
from ..authentication.models import User
import re
from rest_framework.pagination import PageNumberPagination
from rest_framework.generics import ListAPIView
from typing import List


class SendEmailView(APIView):
    """
    API to send emails and create Thread/Email records
    Supports both content_plain and content_html
    """

    permission_classes = (IsAuthenticated,)

    def post(self, request):
        try:
            ids_list = request.data.get("ids_list", [])
            if ids_list:
                ids_list = ids_list.split(",") if isinstance(ids_list, str) else ids_list
                ids_list = [int(id.strip()) for id in ids_list if id.strip().isdigit()]

            serializer = SendEmailSerializer(data=request.data)
            if serializer.is_valid():
                email_service = EmailService()
                files = request.FILES.getlist("attachments")
                attachment_paths = []
                temp_files = []

                # Handle file attachments with proper filenames
                for file in files:
                    # Clean the filename to avoid SES issues
                    clean_filename = self._clean_uploaded_filename(file.name)

                    # Create temporary directory for proper filename handling
                    temp_dir = tempfile.mkdtemp()
                    # Create file with cleaned filename in temp directory
                    temp_file_path = os.path.join(temp_dir, clean_filename)

                    with open(temp_file_path, "wb") as f:
                        for chunk in file.chunks():
                            f.write(chunk)

                    attachment_paths.append(temp_file_path)
                    temp_files.append(temp_file_path)
                    temp_files.append(temp_dir)  # Also track directory for cleanup

                # Send email and create records
                result = email_service.send_email_and_create_record(
                    serializer.validated_data, request.user, attachment_paths, ids_list
                )

                if not result["success"]:
                    # Clean up temp files and directories on failure
                    for temp_item in temp_files:
                        try:
                            if os.path.isfile(temp_item):
                                os.remove(temp_item)
                            elif os.path.isdir(temp_item):
                                import shutil

                                shutil.rmtree(temp_item)
                        except Exception as e:
                            print(f"Could not remove temp item: {e}")
                    return Response(
                        {"error": result["error"]}, status=status.HTTP_400_BAD_REQUEST
                    )

                # Get the created email record
                email_id = result["email_id"]
                email_record = Email.objects.get(id=email_id)
                user = request.user

                # Upload attachments to S3 and create attachment records
                s3_client = S3Client()
                bucket_name = os.getenv("AWS_STORAGE_BUCKET_VOUCHER")
                folder_name = os.getenv("AWS_FOLDER_NAME")

                for file, tmp_path in zip(files, attachment_paths):
                    # Use the cleaned filename for database storage
                    clean_filename = os.path.basename(tmp_path)
                    file_url = None

                    if clean_filename.lower().endswith(".pdf"):
                        upload_result = s3_client.upload_file(
                            tmp_path, bucket_name, folder_name, clean_filename
                        )
                        if upload_result.get("status") == 200:
                            file_url = upload_result.get("url")

                    EmailAttachment.objects.create(
                        user=user,
                        email=email_record,
                        filename=clean_filename,  # Use cleaned filename
                        file_url=file_url,
                        file_size=str(file.size),
                        attachment_type="USER_UPLOADED",
                    )

                # Clean up temporary files and directories
                for temp_item in temp_files:
                    try:
                        if os.path.isfile(temp_item):
                            os.remove(temp_item)
                        elif os.path.isdir(temp_item):
                            import shutil

                            shutil.rmtree(temp_item)
                    except Exception as e:
                        print(f"Could not remove temp item: {e}")

                return Response(
                    {
                        "message": "Email sent successfully",
                        "data": result,
                        "email_id": email_id,
                        "thread_id": result["thread_id"],
                    },
                    status=status.HTTP_201_CREATED,
                )

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _clean_uploaded_filename(self, filename):
        """
        Clean uploaded filename to prevent SES issues
        """
        import re

        # Replace multiple underscores with single underscore
        filename = re.sub(r"_{2,}", "_", filename)

        # Replace spaces with underscores
        filename = filename.replace(" ", "_")

        # Remove problematic characters
        filename = re.sub(r'[<>:"/\\|?*]', "", filename)

        # Remove parentheses
        filename = filename.replace("(", "").replace(")", "")

        # Ensure filename is not too long
        if len(filename) > 100:
            name, ext = os.path.splitext(filename)
            filename = name[:95] + ext

        return filename


# class ThreadListView(APIView):
#     """
#     API to list user's threads
#     """

#     permission_classes = (IsAuthenticated,)

#     def get(self, request):
#         try:
#             # Get the user_id
#             user_id = request.user.id

#             threads = Thread.objects.filter(user=request.user).order_by("-updated_at")
#             serializer = ThreadSerializer(threads, many=True)
#             return Response(serializer.data)
#         except Exception as e:
#             return Response(
#                 {"error": f"Error fetching threads: {str(e)}"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "pageSize"
    max_page_size = 100

    def get_paginated_response(self, data):
        # Return raw data without any wrapper
        return Response(data)


class ThreadListView(ListAPIView):
    """
    API to list user's threads with pagination
    """

    serializer_class = ThreadSerializer
    permission_classes = (IsAuthenticated,)
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        # Only return threads for the authenticated user
        return Thread.objects.filter(user=self.request.user).order_by("-updated_at")

    def list(self, request, *args, **kwargs):
        try:
            # Get the page number from query params, default to 1
            page = request.query_params.get("page", 1)
            try:
                page = int(page)
            except (TypeError, ValueError):
                page = 1

            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)

            if page is not None:
                serializer = self.get_serializer(page, many=True)
                formatted_data = []
                for thread in serializer.data:
                    formatted_data.append(
                        {
                            "id": thread.get("id"),
                            "subject": thread.get("subject"),
                            "to_email": thread.get("to_email"),
                            "created_at": thread.get("created_at"),
                            "vendor_name": thread.get("vendor_name"),
                            "supplier_name": thread.get("supplier_name"),
                            "vendor_gstin": thread.get("vendor_gstin"),
                            "created_at": thread.get("created_at"),
                        }
                    )

                return Response(
                    {"threadCount": queryset.count(), "threads": formatted_data}
                )

            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)

        except Exception as e:
            return Response(
                {"error": f"Error fetching threads: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class ThreadDetailView(APIView):
    """
    API to get thread details with all emails
    """

    permission_classes = (IsAuthenticated,)

    def get(self, request, thread_id):
        try:
            # Get the user_id
            user_id = request.user.id

            thread = Thread.objects.get(id=thread_id, user=request.user)
            emails = Email.objects.filter(thread=thread, user=request.user).order_by(
                "created_at"
            )

            thread_data = ThreadSerializer(thread).data
            emails_data = EmailSerializer(emails, many=True).data

            return Response({"thread": thread_data, "emails": emails_data})
        except Thread.DoesNotExist:
            return Response(
                {"error": "Thread not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Error fetching thread details: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class EmailReplyProcessView(APIView):
    """
    Process incoming email replies using parsed email data
    Note: This endpoint doesn't require authentication as it's called by SES webhook
    """

    def post(self, request):
        try:
            messageID = request.data["Records"][0]["ses"]["mail"]["messageId"]
            read_bucket = "ae-email-reciever"
            s3_client = boto3.client("s3")
            response = s3_client.get_object(Bucket=read_bucket, Key=messageID)
            content = response["Body"].read().decode("utf-8")
            parsed_email = parse_email_payload_complete(content)
            headers = parsed_email.get("headers", {})
            body = parsed_email.get("body", {})
            attachments = parsed_email.get("attachments", [])
            from_email = self._extract_email_address(headers.get("from", ""))
            to_email = self._extract_email_address(headers.get("to", ""))
            cc_email = headers.get("cc", "") or ""
            bcc_email = headers.get("bcc", "") or ""
            subject = headers.get("subject", "No Subject")
            message_id = headers.get("message-id", f"<unknown-{messageID}>")
            in_reply_to = headers.get("in-reply-to") or ""
            references = headers.get("references") or ""
            date_header = headers.get("date")
            content_plain = body.get("text", "")
            content_html = body.get("html", "")
            reply_message = content_html if content_html else content_plain
            thread = None
            reply_to_email = None
            user = None
            # Clean the in_reply_to message id
            in_reply_to_clean = clean_message_id(in_reply_to)
            print("In reply to mail is:", in_reply_to_clean)
            if in_reply_to_clean:
                try:
                    reply_to_email = Email.objects.get(message_id=in_reply_to_clean)
                    thread = reply_to_email.thread
                    user = reply_to_email.user  # Use the user from the replied email
                except Email.DoesNotExist:
                    pass
            if not thread and references:
                ref_ids = references.split()
                for ref_id in ref_ids:
                    ref_id_clean = clean_message_id(ref_id)
                    try:
                        ref_email = Email.objects.get(message_id=ref_id_clean)
                        thread = ref_email.thread
                        user = ref_email.user
                        break
                    except Email.DoesNotExist:
                        continue
            # Ensure user is found before proceeding
            if not user:
                return Response(
                    {
                        "error": "Could not determine user for this email reply (no matching original email found)."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not thread:
                thread = Thread.objects.create(
                    user=user,
                    subject=subject,
                    to_email=to_email,
                )
            # Clean message_id and in_reply_to before saving
            cleaned_message_id = clean_message_id(message_id)
            cleaned_in_reply_to = clean_message_id(in_reply_to)
            email_data = {
                "message_id": cleaned_message_id,
                "thread": thread.pk,
                "reply_to": reply_to_email.pk if reply_to_email else None,
                "from_email": from_email,
                "to_email": to_email,
                "cc_email": cc_email,
                "bcc_email": bcc_email,
                "subject": subject,
                "in_reply_to": cleaned_in_reply_to,
                "references": references,
                "date": str(self._parse_email_date(date_header)),
                "reply_message": reply_message,
                "raw_body": content,
                "content_plain": content_plain,
                "content_html": content_html,
                "email_type": "received",
            }
            print("response data:", email_data)

            email_serializer = EmailSerializer(data=email_data)
            if email_serializer.is_valid():
                try:
                    email_record = email_serializer.save(user=user)
                    if not thread.first_email:
                        thread.first_email = email_record
                        thread.save()

                    # Check if this is a reply to an email that has reminders enabled
                    # and update the reminder status to 0 (reply received)
                    if reply_to_email:
                        try:
                            # Traverse up the reply_to chain to find the root/original email
                            root_email = reply_to_email
                            while root_email.reply_to is not None:
                                root_email = root_email.reply_to
                            # Now root_email is the original email in the chain
                            try:
                                email_reminder = EmailReminders.objects.get(
                                    message_id=root_email.message_id
                                )
                                # Update reminder status to 0 (reply received)
                                email_reminder.reminder_status = 0
                                email_reminder.reminder_enabled = (
                                    False  # Disable further reminders
                                )
                                email_reminder.save()
                                print(
                                    f"Updated reminder status for email {root_email.message_id} - reply received"
                                )
                            except EmailReminders.DoesNotExist:
                                # No reminder found for this email, which is fine
                                pass
                            except Exception as e:
                                print(f"Error updating reminder status: {e}")
                        except Exception as e:
                            print(f"Error traversing reply_to chain: {e}")

                    s3_client = S3Client()
                    bucket_name = os.getenv("AWS_STORAGE_BUCKET_VOUCHER")
                    folder_name = os.getenv("AWS_FOLDER_NAME")
                    for attachment in attachments:
                        filename = attachment.get("filename", "unknown_attachment")
                        binary_content = attachment.get("binary_content")
                        file_url = None
                        tmp_file_path = None
                        if binary_content:
                            with tempfile.NamedTemporaryFile(
                                delete=False, suffix=os.path.splitext(filename)[-1]
                            ) as tmp_file:
                                tmp_file.write(binary_content)
                                tmp_file_path = tmp_file.name
                            if filename.lower().endswith(".pdf"):
                                upload_result = s3_client.upload_file(
                                    tmp_file_path, bucket_name, folder_name, filename
                                )
                                if upload_result.get("status") == 200:
                                    file_url = upload_result.get("url")
                            EmailAttachment.objects.create(
                                user=user,
                                email=email_record,
                                filename=filename,
                                file_url=file_url,
                                file_size=str(len(binary_content)),
                                attachment_type="SYSTEM_GENERATED",
                            )
                            try:
                                os.remove(tmp_file_path)
                            except Exception as e:
                                print(f"Could not remove temp file: {e}")
                    return Response(
                        {
                            "success": True,
                            "email_id": email_record.pk,
                            "thread_id": thread.id,
                            "message": "Email processed successfully",
                            "attachments_count": len(attachments),
                        },
                        status=status.HTTP_201_CREATED,
                    )
                except Exception as e:
                    print(f"Error saving email: {e}")
                    traceback.print_exc()
                    return Response(
                        {"error": f"Error saving email: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
            else:
                print("Email serializer errors:", email_serializer.errors)
                traceback.print_exc()
                return Response(
                    {"error": "Invalid email data", "details": email_serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except KeyError as e:
            print(f"Missing required field in SES data: {e}")
            traceback.print_exc()
            return Response(
                {"error": f"Missing required field: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            print("Unhandled Exception:", str(e))
            traceback.print_exc()
            return Response(
                {"error": f"Unhandled Exception: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _extract_email_address(self, email_field):
        """Extract email address from header field that might contain name and email"""
        if not email_field:
            return ""

        # Handle format like "Name <email@domain.com>"
        email_match = re.search(r"<([^>]+)>", email_field)
        if email_match:
            return email_match.group(1)

        # Handle format like "email@domain.com"
        email_match = re.search(r"([^\s<>@,;]+@[^\s<>@,;]+)", email_field)
        if email_match:
            return email_match.group(1)

        return email_field.strip()

    def _parse_email_date(self, date_header):
        """Parse email date header"""
        if not date_header:
            return None

        try:
            from email.utils import parsedate_to_datetime

            return parsedate_to_datetime(date_header)
        except Exception as e:
            print(f"Error parsing date '{date_header}': {e}")
            return None
