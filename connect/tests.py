from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from .models import EmailReply

# Create your tests here.


class EmailReplyAPITest(APITestCase):
    def test_create_email_reply(self):
        raw_body = """From: omuamua asteroid <omuamuaasteroid@gmail.com>\nTo: Edge GST <akib@gst.auditedge.in>\nSubject: Re: Test Email two\nMessage-ID: <CAA+MKmExzFDwSf=Q=C3qnC5ZU_e=cbA1Yr8m9avDm5gq5SV4oQ@mail.gmail.com>\nIn-Reply-To: <01000197968c3549-0a91f03d-b4a9-4239-b06b-85a681da7180-000000@email.amazonses.com>\nDate: Sun, 22 Jun 2025 13:01:25 +0530\nContent-Type: text/html; charset=\"UTF-8\"\n\n<div dir=3D\"ltr\">Replying to message two</div>\n"""
        url = reverse("email-reply-create")
        response = self.client.post(url, {"raw_body": raw_body}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("reply_message", response.data)
        self.assertEqual(response.data["reply_message"], "Replying to message two")
