import json

from django.db import models
from ..core.models import CoreModel
from apps.authentication.models import UserGstInfo, User

class PrDataTransactions(CoreModel):
    ERROR_CHOICES = [(1, "Failure"), (0, "Success"), (2, "Transaction Failed")]

    user_gst_info = models.ForeignKey(
        UserGstInfo, on_delete=models.CASCADE, related_name="pr_data_entries"
    )
    period_start = models.DateField()
    period_end = models.DateField()

    validation_errors_details = models.TextField()
    validation_error_status = models.IntegerField(choices=ERROR_CHOICES, null=True, blank=True)

    filename = models.TextField(default=None, null=True, blank=True)
    s3_link = models.TextField(null=True, blank=True)
    upload_type = models.CharField(max_length=20, null=True, blank=True)
    upload_period = models.CharField(max_length=20, null=True, blank=True)
    upload_error_status = models.BooleanField(default=False, null=True, blank=True)
    upload_errors = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.month}-{self.year}: {self.user_gst_info.gstin}"

class TimeRange(CoreModel):
    MONTH_CHOICES = [(i, i) for i in range(1, 13)]

    QUARTER_CHOICES = [(1, "Q1"), (2, "Q2"), (3, "Q3"), (4, "Q4")]

    PROCESS_CHOICES = [
        (0, "uninitiated"),
        (1, "in_progress"),
        (2, "completed"),
        (3, "failed"),
    ]

    id = models.AutoField(primary_key=True)

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="time_range_user"
    )
    user_gst_info = models.ForeignKey(
        UserGstInfo, on_delete=models.CASCADE, related_name="time_range_details"
    )

    Month = models.IntegerField(choices=MONTH_CHOICES)
    Year = models.IntegerField()
    Quarter = models.IntegerField(choices=QUARTER_CHOICES)
    FY = models.CharField(max_length=10)

    status_PR = models.BooleanField(default=False)
    status_2B = models.IntegerField(choices=PROCESS_CHOICES, default=0)
    status_reco = models.IntegerField(choices=PROCESS_CHOICES, default=0)
    status_adv_reco = models.IntegerField(choices=PROCESS_CHOICES, default=0)
    status_upload = models.BooleanField(default=True)
    status_validation_errors = models.BooleanField(default=False, blank=True, null=True)
    status_data_edited = models.BooleanField(default=False, blank=True, null=True)

    no_of_doc_PR = models.IntegerField()
    no_of_doc_2B = models.IntegerField()
    tax_difference = models.DecimalField(max_digits=20, decimal_places=2)
    itc_PR = models.DecimalField(max_digits=20, decimal_places=2)
    itc_2B = models.DecimalField(max_digits=20, decimal_places=2)

    def __str__(self):
        return f"{self.Month}/{self.Year}"


class PrData(CoreModel):
    id = models.AutoField(primary_key=True)

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="pr_data_user"
    )
    user_gst_info = models.ForeignKey(
        UserGstInfo, on_delete=models.CASCADE, related_name="pr_data_details"
    )

    reconciliation_status = models.BooleanField(default=False, null=True, blank=True)
    reconciliation_category = models.CharField(max_length=20, blank=True, null=True)

    supplier_gstin = models.CharField(max_length=15, null=True, blank=True)
    supplier_name = models.CharField(max_length=255, null=True, blank=True)
    document_type = models.CharField(max_length=50, null=True, blank=True)
    inter_intra = models.CharField(max_length=20, null=True, blank=True)
    user_gstin = models.CharField(max_length=15, null=True, blank=True)
    return_period = models.CharField(max_length=10, null=True, blank=True)

    document_number = models.CharField(max_length=50, null=True, blank=True)
    document_date = models.DateField(null=True, blank=True)
    accounting_date = models.DateField(null=True, blank=True)
    place_of_supply = models.CharField(max_length=50, null=True, blank=True)

    invoice_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    taxable_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    igst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, null=True, blank=True)
    cgst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, null=True, blank=True)
    sgst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, null=True, blank=True)
    cess = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, null=True, blank=True)

    internal_reference_document_number = models.TextField(blank=True, null=True)
    internal_counter_party_code = models.TextField(blank=True, null=True)
    plant_code = models.TextField(blank=True, null=True)
    internal_field_1 = models.TextField(blank=True, null=True)
    internal_field_2 = models.TextField(blank=True, null=True)
    internal_field_3 = models.TextField(blank=True, null=True)
    internal_field_4 = models.TextField(blank=True, null=True)
    internal_field_5 = models.TextField(blank=True, null=True)
    
    upload_type = models.CharField(max_length=20, null=True, blank=True)

    guid = models.CharField(max_length=100, null=True, blank=True)
    voucher_number = models.CharField(max_length=100, null=True, blank=True)
    voucher_type = models.CharField(max_length=100, null=True, blank=True)

    duplicate_status = models.BooleanField(default=False, null=True, blank=True)
    duplicate_errors = models.TextField(null=True, blank=True)
    validation_error_status = models.BooleanField(default=False, null=True, blank=True)
    validation_errors = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.id} : {self.user_gst_info.gstin}"


class Data2B(CoreModel):
    id = models.AutoField(primary_key=True)

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="data_2b_user"
    )
    user_gst_info = models.ForeignKey(
        UserGstInfo, on_delete=models.CASCADE, related_name="data_2b_details"
    )

    supplier_gstin = models.CharField(max_length=15)
    supplier_name = models.CharField(max_length=255)
    user_gstin = models.CharField(max_length=15)
    
    return_period = models.CharField(max_length=10)
    document_number = models.CharField(max_length=50)
    document_date = models.DateField()
    section = models.CharField(max_length=20)

    taxable_value = models.DecimalField(max_digits=15, decimal_places=2)
    invoice_value = models.DecimalField(max_digits=15, decimal_places=2)
    cgst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    sgst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    igst = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    cess = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    document_type = models.CharField(max_length=50)
    place_of_supply = models.CharField(max_length=100)
    note_supply_type = models.CharField(max_length=50, blank=True, null=True)

    supply_attract_reverse_charge = models.CharField(max_length=50)
    gst_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    supplier_filing_date = models.DateField(blank=True, null=True)
    supplier_filing_period = models.CharField(max_length=10, blank=True, null=True)

    itc_availability = models.CharField(max_length=50)
    itc_unavailability_reason = models.TextField(blank=True, null=True)

    applicable_percent_of_tax_rate = models.CharField(
        max_length=10, blank=True, null=True
    )
    source = models.CharField(max_length=50)
    irn = models.CharField(max_length=100, blank=True, null=True)
    irn_generated_date = models.CharField(max_length=100, blank=True, null=True)
    inter_or_intra = models.CharField(max_length=20)

    reconciliation_status = models.BooleanField(default=False)
    reconciliation_category = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.id} : {self.user_gst_info.gstin}"


class ReconciliationReport(CoreModel):
    id = models.AutoField(primary_key=True)

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="reco_data_user"
    )
    user_gstin = models.ForeignKey(
        UserGstInfo, on_delete=models.CASCADE, related_name="reco_data_details"
    )

    link_status = models.CharField(
        max_length=50, default="basic"
    )  # basic, linked, delinked, advanced(in future)
    link_range = models.CharField(max_length=50, default=None, null=True)

    # GSTIN Information
    GSTIN_of_User = models.CharField(max_length=255, blank=True, null=True)
    GSTIN_of_Supplier_2B = models.CharField(max_length=255, blank=True, null=True)
    GSTIN_of_Supplier_PR = models.CharField(max_length=255, blank=True, null=True)

    # Invoice Information
    Supplier_Invoice_Number_2B = models.CharField(max_length=255, blank=True, null=True)
    Supplier_Invoice_Number_PR = models.CharField(max_length=255, blank=True, null=True)
    Supplier_Invoice_Date_2B = models.CharField(max_length=255, blank=True, null=True)
    Supplier_Invoice_Date_PR = models.CharField(max_length=255, blank=True, null=True)

    # Note Information
    Supplier_Note_Number_2B = models.CharField(max_length=255, blank=True, null=True)
    Supplier_Note_Number_PR = models.CharField(max_length=255, blank=True, null=True)
    Supplier_Note_Date_2B = models.CharField(max_length=255, blank=True, null=True)
    Supplier_Note_Date_PR = models.CharField(max_length=255, blank=True, null=True)

    # Classification
    Category = models.CharField(max_length=255, blank=True, null=True)
    Document_Type = models.CharField(max_length=255, blank=True, null=True)
    Section = models.CharField(max_length=255, blank=True, null=True)

    # Fiscal Information
    FY_of_Invoice_PR = models.CharField(max_length=255, blank=True, null=True)
    FY_of_Invoice_2B = models.CharField(max_length=255, blank=True, null=True)
    Period_PR = models.CharField(max_length=255, blank=True, null=True)
    Period_2B = models.CharField(max_length=255, blank=True, null=True)

    # Supplier Details
    Name_of_Supplier_2B = models.CharField(max_length=255, blank=True, null=True)
    Name_of_Supplier_PR = models.CharField(max_length=255, blank=True, null=True)
    Place_of_Supply_PR = models.CharField(max_length=255, blank=True, null=True)
    Place_of_Supply_2B = models.CharField(max_length=255, blank=True, null=True)

    # Value Information
    Invoice_Value_PR = models.CharField(max_length=255, blank=True, null=True)
    Invoice_Value_2B = models.CharField(max_length=255, blank=True, null=True)
    Invoice_Value_Difference = models.CharField(max_length=255, blank=True, null=True)
    Taxable_Value_PR = models.CharField(max_length=255, blank=True, null=True)
    Taxable_Value_2B = models.CharField(max_length=255, blank=True, null=True)
    Taxable_Value_Difference = models.CharField(max_length=255, blank=True, null=True)

    # Tax Information
    IGST_PR = models.CharField(max_length=255, blank=True, null=True)
    IGST_2B = models.CharField(max_length=255, blank=True, null=True)
    IGST_difference = models.CharField(max_length=255, blank=True, null=True)
    CGST_PR = models.CharField(max_length=255, blank=True, null=True)
    CGST_2B = models.CharField(max_length=255, blank=True, null=True)
    CGST_difference = models.CharField(max_length=255, blank=True, null=True)
    SGST_PR = models.CharField(max_length=255, blank=True, null=True)
    SGST_2B = models.CharField(max_length=255, blank=True, null=True)
    SGST_difference = models.CharField(max_length=255, blank=True, null=True)
    Total_tax_PR = models.CharField(max_length=255, blank=True, null=True)
    Total_tax_2B = models.CharField(max_length=255, blank=True, null=True)
    Total_Tax_Difference = models.CharField(max_length=255, blank=True, null=True)
    Cess_PR = models.CharField(max_length=255, blank=True, null=True)
    Cess_2B = models.CharField(max_length=255, blank=True, null=True)

    # Other Information
    ITC_Availability_2B = models.CharField(max_length=255, blank=True, null=True)
    Reason = models.CharField(max_length=255, blank=True, null=True)
    Warning = models.CharField(max_length=255, blank=True, null=True)
    Supply_attract_reverse_charge_2B = models.CharField(
        max_length=255, blank=True, null=True
    )
    Reason_for_Categorization = models.CharField(max_length=255, blank=True, null=True)
    User_Comments = models.CharField(max_length=255, blank=True, null=True)

    # Tracking Information
    Last_Action_Taken = models.CharField(max_length=255, blank=True, null=True)
    Timestamp_of_Last_Action = models.CharField(max_length=255, blank=True, null=True)
    User_Identification = models.CharField(max_length=255, blank=True, null=True)
    vendor_communication_status = models.BooleanField(default=False)

    # Additional Details
    Inter_or_Intra_2B = models.CharField(max_length=255, blank=True, null=True)
    Transaction_id_pr = models.CharField(max_length=255, blank=True, null=True)
    Transaction_id_2b = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.id} : {self.user_gstin.gstin}"


class UserModificationHistory(CoreModel):
    id = models.AutoField(primary_key=True)

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="reco_data_history_user"
    )
    user_gstin = models.ForeignKey(
        UserGstInfo, on_delete=models.CASCADE, related_name="reco_data_history_details"
    )

    link_status = models.CharField(max_length=50)  # linked, delinked
    link_range = models.CharField(max_length=50, default=None, null=True)

    # GSTIN Information
    GSTIN_of_User = models.CharField(max_length=255, blank=True, null=True)
    GSTIN_of_Supplier_2B = models.CharField(max_length=255, blank=True, null=True)
    GSTIN_of_Supplier_PR = models.CharField(max_length=255, blank=True, null=True)

    # Invoice Information
    Supplier_Invoice_Number_2B = models.CharField(max_length=255, blank=True, null=True)
    Supplier_Invoice_Number_PR = models.CharField(max_length=255, blank=True, null=True)
    Supplier_Invoice_Date_2B = models.CharField(max_length=255, blank=True, null=True)
    Supplier_Invoice_Date_PR = models.CharField(max_length=255, blank=True, null=True)

    # Note Information
    Supplier_Note_Number_2B = models.CharField(max_length=255, blank=True, null=True)
    Supplier_Note_Number_PR = models.CharField(max_length=255, blank=True, null=True)
    Supplier_Note_Date_2B = models.CharField(max_length=255, blank=True, null=True)
    Supplier_Note_Date_PR = models.CharField(max_length=255, blank=True, null=True)

    # Classification
    Category = models.CharField(max_length=255, blank=True, null=True)
    Document_Type = models.CharField(max_length=255, blank=True, null=True)
    Section = models.CharField(max_length=255, blank=True, null=True)

    # Fiscal Information
    FY_of_Invoice_PR = models.CharField(max_length=255, blank=True, null=True)
    FY_of_Invoice_2B = models.CharField(max_length=255, blank=True, null=True)
    Period_PR = models.CharField(max_length=255, blank=True, null=True)
    Period_2B = models.CharField(max_length=255, blank=True, null=True)

    # Supplier Details
    Name_of_Supplier_2B = models.CharField(max_length=255, blank=True, null=True)
    Name_of_Supplier_PR = models.CharField(max_length=255, blank=True, null=True)
    Place_of_Supply_PR = models.CharField(max_length=255, blank=True, null=True)
    Place_of_Supply_2B = models.CharField(max_length=255, blank=True, null=True)

    # Value Information
    Invoice_Value_PR = models.CharField(max_length=255, blank=True, null=True)
    Invoice_Value_2B = models.CharField(max_length=255, blank=True, null=True)
    Invoice_Value_Difference = models.CharField(max_length=255, blank=True, null=True)
    Taxable_Value_PR = models.CharField(max_length=255, blank=True, null=True)
    Taxable_Value_2B = models.CharField(max_length=255, blank=True, null=True)
    Taxable_Value_Difference = models.CharField(max_length=255, blank=True, null=True)

    # Tax Information
    IGST_PR = models.CharField(max_length=255, blank=True, null=True)
    IGST_2B = models.CharField(max_length=255, blank=True, null=True)
    IGST_difference = models.CharField(max_length=255, blank=True, null=True)
    CGST_PR = models.CharField(max_length=255, blank=True, null=True)
    CGST_2B = models.CharField(max_length=255, blank=True, null=True)
    CGST_difference = models.CharField(max_length=255, blank=True, null=True)
    SGST_PR = models.CharField(max_length=255, blank=True, null=True)
    SGST_2B = models.CharField(max_length=255, blank=True, null=True)
    SGST_difference = models.CharField(max_length=255, blank=True, null=True)
    Total_tax_PR = models.CharField(max_length=255, blank=True, null=True)
    Total_tax_2B = models.CharField(max_length=255, blank=True, null=True)
    Total_Tax_Difference = models.CharField(max_length=255, blank=True, null=True)
    Cess_PR = models.CharField(max_length=255, blank=True, null=True)
    Cess_2B = models.CharField(max_length=255, blank=True, null=True)

    # Other Information
    ITC_Availability_2B = models.CharField(max_length=255, blank=True, null=True)
    Reason = models.CharField(max_length=255, blank=True, null=True)
    Warning = models.CharField(max_length=255, blank=True, null=True)
    Supply_attract_reverse_charge_2B = models.CharField(
        max_length=255, blank=True, null=True
    )
    Reason_for_Categorization = models.CharField(max_length=255, blank=True, null=True)
    User_Comments = models.CharField(max_length=255, blank=True, null=True)

    # Tracking Information
    Last_Action_Taken = models.CharField(max_length=255, blank=True, null=True)
    Timestamp_of_Last_Action = models.CharField(max_length=255, blank=True, null=True)
    User_Identification = models.CharField(max_length=255, blank=True, null=True)

    # Additional Details
    Inter_or_Intra_2B = models.CharField(max_length=255, blank=True, null=True)
    Transaction_id_pr = models.CharField(max_length=255, blank=True, null=True)
    Transaction_id_2b = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.id} : {self.user_gstin.gstin}"


class Notifications(CoreModel):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE, 
        related_name='user_notifications',
    )
    user_gst_info = models.ForeignKey(
        UserGstInfo, 
        on_delete=models.CASCADE, 
        null=True, blank=True, # Nullable if a notification isn't GSTIN-specific
        related_name='user_gst_notifications',
    )

    module = models.CharField(
        max_length=50,
        choices=[
            ("reconciliation", "Reconciliation"),
            ("data_2b_fetch", "GSTR-2B Fetch"),
            ("zoho_fetch", "Zoho Data Fetch"),
            ("tally_fetch", "Tally Data Fetch"), 
        ],
        help_text="The specific module within the app (e.g., 'reconciliation', 'data_2b_fetch')."
    )

    title = models.CharField(
        max_length=255,
        help_text="A concise title for the notification."
    )

    message = models.TextField(
        help_text="The main content or details of the notification."
    )

    type = models.CharField(
        max_length=20,
        choices=[
            ("success", "Success"),
            ("error", "Error"),
            ("info", "Info"),
            ("warning", "Warning"),
        ],
        default="info",
        help_text="The type/severity of the notification."
    )

    priority = models.CharField(
        max_length=20, 
        default="normal", 
        help_text="The priority level of the notification."
    )
   
    # Metadata Fields (JSONField for flexibility)
    metadata = models.JSONField(
        default=dict, 
        blank=True, null=True,
        help_text="Additional key-value pairs related to the notification (e.g., financial_year, quarter, months, status, record_count)."
    )

    # Timestamp & Status
    timestamp = models.DateTimeField(
        auto_now_add=True, # Automatically sets on creation
        help_text="The time when the notification was created."
    )

    read = models.BooleanField(
        default=False, 
        help_text="Indicates if the notification has been read by the user."
    )

    expires_at = models.DateTimeField(
        null=True, blank=True, 
        help_text="Timestamp when the notification should expire."
    )

    thread_id = models.CharField(
        max_length=255, 
        blank=True, null=True, 
        help_text="Identifier to group related notifications."
    )

    action_type = models.CharField(
        max_length=255,
        blank=True, null=True,
    )

    action_label = models.CharField(
        max_length=255,
        blank=True, null=True,
    )

    action_url = models.CharField(
        max_length=255,
        blank=True, null=True,
    )

    action_app = models.CharField(
        max_length=255,
        blank=True, null=True,
    )


    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f"[{self.get_type_display()}] {self.title} for {self.user.username} ({self.gstin or 'N/A'})"

    def to_websocket_format(self):
        """
        Converts the Notification object to the specified WebSocket JSON format.
        Pulls GSTIN and name from the related UserGstInfo object.
        """
        
        # Populate gstin_details from user_gst_info if available
        gstin_details = {
            "gstin": self.user_gst_info.gstin if self.user_gst_info else None,
            "name": self.user_gst_info.company_name if self.user_gst_info else None
        }

        # Company ID is currently empty as per your instruction
        company_id_val = "" 

        # User ID from the related user object
        user_id_val = str(self.user.id) # Ensure it's a string

        # Ensure metadata is a dictionary, even if stored as None/null
        metadata_payload = self.metadata if self.metadata is not None else {}
        
        # Actions are now directly on the model, default values are set in the model definition
        actions_payload = {
            "type": self.action_type,
            "label": self.action_label,
            "url": self.action_url,
            "app": self.action_app
        }

        return {
            "type": "notification",
            "event": "new_notification",
            "data": {
                "id": str(self.id), # Convert UUID or int ID to string
                "app": "gst",
                "module": self.module,
                "title": self.title,
                "message": self.message,
                "type": self.type,
                "priority": self.priority,
                "context": {
                    "gstin_details": gstin_details,
                    "company_id": company_id_val,
                    "user_id": user_id_val
                },
                "metadata": metadata_payload,
                "timestamp": self.timestamp.isoformat().replace('+00:00', 'Z') if self.timestamp else None,
                "read": self.read,
                "expires_at": self.expires_at.isoformat().replace('+00:00', 'Z') if self.expires_at else None,
                "actions": actions_payload,
                "thread_id": self.thread_id if self.thread_id else "" # Ensure empty string if null
            }
        }