import calendar
import pandas as pd
from pytz import timezone
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.db.models import (
    Q,
    F,
    Sum,
    Count
)
from django.db.models import Sum, F, DecimalField
from django.db.models.functions import Cast
from django.utils.timezone import localtime

from rest_framework import serializers

from .models import (
    PrData,
    Data2B,
    Notifications,
    ReconciliationReport,  
    PrDataTransactions,
    TimeRange
)

from .utils import format_date
 
class PrDataTransactionsSerializer(serializers.ModelSerializer):
    created_at_ist = serializers.SerializerMethodField()

    class Meta:
        model = PrDataTransactions
        fields = ['id', 'created_at_ist', 'filename', 'upload_type', 'upload_period', 'upload_error_status', 'upload_errors']

    def get_created_at_ist(self, obj):
        ist = timezone('Asia/Kolkata')  
        return localtime(obj.created_at, ist).strftime('%d-%m-%Y %H:%M:%S')

class PrDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrData
        fields = [
            'id',

            'reconciliation_status',
            'reconciliation_category',

            "document_number",
            "document_date",
            "accounting_date",

            "supplier_gstin",
            "supplier_name",
            "user_gstin",

            "invoice_value",
            "taxable_value",
            "igst",
            "cgst",
            "sgst",

            "document_type",

            "duplicate_status",
            "duplicate_errors",
            "validation_error_status",
            "validation_errors",
            
        ]

class PRSuggestionsDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrData
        fields = [
            "document_number",
            "document_date",
            "supplier_gstin",
            "place_of_supply",
            "invoice_value",
            "taxable_value",
            "igst",
            "cgst",
            "sgst",
            "cess",
            "document_type"
        ]
 
class Data2bSuggestionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Data2B
        fields = [
            "document_number",
            "document_date",
            "supplier_gstin",
            "place_of_supply",
            "invoice_value",
            "taxable_value",
            "igst",
            "cgst",
            "sgst",
            "cess",
            "document_type"
        ]

class PopupSerializer(serializers.Serializer):
    No_of_documents = serializers.IntegerField()
    Total_tax = serializers.IntegerField()
    cgst = serializers.IntegerField()
    sgst = serializers.IntegerField()
    igst = serializers.IntegerField()

    @classmethod
    def get_summary(cls, queryset):
        summary = queryset.aggregate(
            No_of_documents=Count('id'),
            cgst=Sum(Cast('cgst', output_field=models.FloatField()), default=0),
            sgst=Sum(Cast('sgst', output_field=models.FloatField()), default=0),
            igst=Sum(Cast('igst', output_field=models.FloatField()), default=0)
        )
        summary = {key: int(round(value)) for key, value in summary.items()}
        summary["Total_tax"] = summary["cgst"] + summary["sgst"] + summary["igst"]
        return cls(summary).data

class PopupMonthSerializerPR(serializers.Serializer):
    month = serializers.CharField()
    state = serializers.SerializerMethodField()

    def get_state(self, obj):
        return "Yes" if obj.status_PR == 1 else "No"

    def to_representation(self, instance):
        return {
            "month": calendar.month_name[int(instance.Month)],
            "availability": self.get_state(instance)
        }

class PopupMonthSerializer2B(serializers.Serializer):
    month = serializers.CharField()
    state = serializers.SerializerMethodField()

    def get_state(self, obj):
        return "Yes" if obj.status_2B == 2 else "No"

    def to_representation(self, instance):
        return {
            "month": calendar.month_name[int(instance.Month)],
            "availability": self.get_state(instance)
        }
        
class data_2b_serializer(serializers.ModelSerializer):
    class Meta:
        model = Data2B
        fields = '__all__'

class RecoInvoiceViewSerializer(serializers.ModelSerializer):
    Invoice_Details = serializers.SerializerMethodField()
    Invoice_Date = serializers.SerializerMethodField()
    Supplier_Details = serializers.SerializerMethodField()
    Taxable_Value = serializers.SerializerMethodField()
    Tax_Value = serializers.SerializerMethodField()
    Total_Value = serializers.SerializerMethodField()
    Return_Period = serializers.SerializerMethodField()
    Action_History = serializers.SerializerMethodField()

    class Meta:
        model = ReconciliationReport
        fields = (
            'id', 'Invoice_Details', 'Invoice_Date', 'Supplier_Details', 'Taxable_Value', 
            'Tax_Value', 'Total_Value', 'Return_Period', 'Action_History', 'Transaction_id_pr', 'Transaction_id_2b', "IGST_PR",     "IGST_2B", "CGST_PR", "CGST_2B", "SGST_PR", "SGST_2B", "Cess_PR", "Cess_2B", "Document_Type", "Place_of_Supply_PR", "Place_of_Supply_2B", "vendor_communication_status"
        )

    def get_Invoice_Details(self, obj):
        return{
            "2B": obj.Supplier_Invoice_Number_2B or obj.Supplier_Note_Number_2B,
            "PR": obj.Supplier_Invoice_Number_PR or obj.Supplier_Note_Number_PR,
            "Category": obj.Category
        }

    def get_Invoice_Date(self, obj):
        return {
            "2B": format_date(obj.Supplier_Invoice_Date_2B or obj.Supplier_Note_Date_2B),
            "PR": format_date(obj.Supplier_Invoice_Date_PR or obj.Supplier_Note_Date_PR)
        }
    
    def get_Supplier_Details(self, obj):
        return {
            "Name": obj.Name_of_Supplier_2B or obj.Name_of_Supplier_PR,
            "GSTIN": obj.GSTIN_of_Supplier_2B or obj.GSTIN_of_Supplier_PR
        }
    
    def get_Taxable_Value(self, obj):
        return {
            "2B": f"{float(obj.Taxable_Value_2B or 0):.2f}",
            "PR": f"{float(obj.Taxable_Value_PR or 0):.2f}"
        }

    def get_Tax_Value(self, obj):
        return {
            "Tax_Difference": f"{float(obj.Total_Tax_Difference or 0):.2f}",
            "2B": f"{float(obj.Total_tax_2B or 0):.2f}",
            "PR": f"{float(obj.Total_tax_PR or 0):.2f}"
        }

    def get_Total_Value(self, obj):
        return {
            "2B": f"{float(obj.Invoice_Value_2B or 0):.2f}",
            "PR": f"{float(obj.Invoice_Value_PR or 0):.2f}"
        }
    
    def format_period(self, period):
        if period:
            month, year = period[:-4], period[-4:] if len(period) > 4 else (period[:-3], period[-3:])
            month_names = {
                "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "Jun",
                "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"
            }
            return f"{month_names.get(month.zfill(2), 'Unknown')} {year}"
        return ""
    
    def get_Return_Period(self, obj):
        return {
            "2B": self.format_period(obj.Period_2B),
            "PR": self.format_period(obj.Period_PR)
        }

    # def get_Action_History(self, obj):
    #     return {
    #         "Match_Type": obj.link_status.capitalize(),
    #         "Comments": obj.User_Comments
    #     }

    def get_Action_History(self, obj):
        if obj.link_status.lower() == "basic":
            match_type = "Auto"
        else:
            match_type = obj.link_status.capitalize()
        return {
            "Match_Type": match_type,
            "Comments": obj.User_Comments
        }
      
class RecoDashboardSerializer(serializers.Serializer):
    Reconciliation_Status = serializers.SerializerMethodField()
    Tax_Difference = serializers.SerializerMethodField()
    PR = serializers.SerializerMethodField()
    B2 = serializers.SerializerMethodField()
    ITC_PR_Sum = serializers.SerializerMethodField()
    ITC_2B_Sum = serializers.SerializerMethodField()
    Monthly_Details = serializers.SerializerMethodField()

    def get_Reconciliation_Status(self, obj):
        records = obj['records']
        completed_months = sum(1 for record in records if record.status_reco == 2)
        total_months = 12  # Always 12 months in a financial year
        return f"{completed_months}/{total_months}"

    def get_Tax_Difference(self, obj):
        records = obj['records']
        tax_diff = sum(record.tax_difference for record in records)
        return f"{tax_diff:.2f}" if tax_diff >= 0 else f"{tax_diff:.2f}"

    def get_PR(self, obj):
        records = obj['records']
        return str(sum(record.no_of_doc_PR for record in records))

    def get_B2(self, obj):
        records = obj['records']
        return str(sum(record.no_of_doc_2B for record in records))

    def get_ITC_PR_Sum(self, obj):
        records = obj['records']
        return f"{sum(record.itc_PR for record in records):.2f}"

    def get_ITC_2B_Sum(self, obj):
        records = obj['records']
        return f"{sum(record.itc_2B for record in records):.2f}"

    def get_Monthly_Details(self, obj):
        records = {record.Month: record for record in obj['records']}
        months = [
            "April", "May", "June", "July", "August", "September",
            "October", "November", "December", "January", "February", "March"
        ]

        monthly_details = []
        for i, month in enumerate(months, start=4):
            if i > 12:
                i -= 12  # Adjust for January-March (FY second part)

            record = records.get(i)
            if record:
                monthly_details.append({
                    "Month": month,
                    "Reconciliation_Status": (
                        "In-Progress" if record.status_reco == 1 else 
                        "Completed" if record.status_reco == 2 else 
                        "Yet To Begin"
                    ),
                    "Advance_Reconciliation_Status": (
                        "In-Progress" if record.status_adv_reco == 1 else 
                        "Completed" if record.status_adv_reco == 2 else 
                        "Yet To Begin"
                    ),
                    "Tax_Difference": f"{record.tax_difference:.2f}" if record.tax_difference >= 0 else f"{record.tax_difference:.2f}",
                    "No_of_Documents_PR": str(record.no_of_doc_PR),
                    "No_of_Documents_2B": str(record.no_of_doc_2B),
                    "ITC_PR": f"{record.itc_PR:.2f}",
                    "ITC_2B": f"{record.itc_2B:.2f}",
                })
            else:
                monthly_details.append({
                    "Month": month,
                    "Reconciliation_Status": "Yet To Begin",
                    "Advance_Reconciliation_Status": "Yet To Begin",
                    "Tax_Difference": "0.00",
                    "No_of_Documents_PR": "",
                    "No_of_Documents_2B": "",
                    "ITC_PR": "0.00",
                    "ITC_2B": "0.00",
                })

        return monthly_details

class DownloadDocumentsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Data2B
        fields = [
            'user_gstin',
            'return_period',
            'section',
            'supplier_gstin',
            'supplier_name',
            'document_type',
            'note_supply_type',
            'document_number',
            'document_date',
            'invoice_value',
            'taxable_value',
            'igst',
            'cgst',
            'sgst',
            'cess',
            'place_of_supply',
            'supply_attract_reverse_charge',
            'supplier_filing_date',
            'supplier_filing_period',
            'itc_availability',
            'itc_unavailablity_reason',
            'applicable_percent_of_tax_rate',
            'source',
            'irn',
            'irn_generated_date',
        ]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        float_fields = [
            'invoice_value',
            'taxable_value',
            'igst',
            'cgst',
            'sgst',
            'cess',
        ]
        for field in float_fields:
            value = rep.get(field)
            if value is not None:
                try:
                    rep[field] = float(value)
                except (ValueError, TypeError):
                    pass  
        return rep

class RecoDetailedReportSerializer(serializers.ModelSerializer):

    class Meta:
        model = ReconciliationReport
        fields = [
            "GSTIN_of_User", 
            "GSTIN_of_Supplier_2B", 
            "GSTIN_of_Supplier_PR",
            
            "Supplier_Invoice_Number_2B", 
            "Supplier_Invoice_Number_PR",
            "Supplier_Invoice_Date_2B", 
            "Supplier_Invoice_Date_PR",
            
            "Supplier_Note_Number_2B", 
            "Supplier_Note_Number_PR",
            "Supplier_Note_Date_2B", 
            "Supplier_Note_Date_PR",
            
            "Category", 
            "Document_Type", 
            "Section",
            
            "FY_of_Invoice_PR", 
            "FY_of_Invoice_2B", 
            
            "Period_PR", 
            "Period_2B",
            
            "Name_of_Supplier_2B", 
            "Name_of_Supplier_PR",
            
            "Place_of_Supply_PR", 
            "Place_of_Supply_2B",
            
            "Invoice_Value_PR", 
            "Invoice_Value_2B", 
            "Invoice_Value_Difference",
            
            "Taxable_Value_PR", 
            "Taxable_Value_2B", 
            "Taxable_Value_Difference",
            
            "IGST_PR", 
            "IGST_2B", 
            "IGST_difference",
            
            "CGST_PR", 
            "CGST_2B", 
            "CGST_difference",
            
            "SGST_PR", 
            "SGST_2B", 
            "SGST_difference",
            
            "Total_tax_PR", 
            "Total_tax_2B", 
            "Total_Tax_Difference",
            
            "Cess_PR", 
            "Cess_2B",
            
            "ITC_Availability_2B", 
            "Reason", 
            "Warning",
            
            "Supply_attract_reverse_charge_2B", 
            "Reason_for_Categorization",
            
            "User_Comments", 
            "Last_Action_Taken", 
            "Timestamp_of_Last_Action",
            
            "User_Identification", 
            "Inter_or_Intra_2B", 
            
            "link_status", 
            "link_range"
        ]
    
    def to_representation(self, instance):
        rep = super().to_representation(instance)
        float_fields = [
            "Invoice_Value_PR", 
            "Invoice_Value_2B", 
            "Invoice_Value_Difference",
            
            "Taxable_Value_PR", 
            "Taxable_Value_2B", 
            "Taxable_Value_Difference",
            
            "IGST_PR", 
            "IGST_2B", 
            "IGST_difference",
            
            "CGST_PR", 
            "CGST_2B", 
            "CGST_difference",
            
            "SGST_PR", 
            "SGST_2B", 
            "SGST_difference",
            
            "Total_tax_PR", 
            "Total_tax_2B", 
            "Total_Tax_Difference",
            
            "Cess_PR", 
            "Cess_2B",
        ]
        for field in float_fields:
            value = rep.get(field)
            if value is not None:
                try:
                    rep[field] = float(value)
                except (ValueError, TypeError):
                    pass  
        return rep

class RecoOverviewReportSerializer(serializers.Serializer):
    """
    Serializer for reconciliation overview report that calculates summary data 
    based on reconciliation records.
    """
    
    @classmethod
    def get_report(cls, queryset):
        """
        Process the queryset directly and return a formatted report.
        """
        # Initialize with zero for safety
        zero_decimal = Decimal('0.00')      

        # Calculate total ITC from all records (first section)
        total_igst_pr = queryset.aggregate(Sum('IGST_PR')).get('IGST_PR__sum') or zero_decimal
        if not isinstance(total_igst_pr, Decimal):
            total_igst_pr = Decimal(str(total_igst_pr))
            
        total_cgst_pr = queryset.aggregate(Sum('CGST_PR')).get('CGST_PR__sum') or zero_decimal
        if not isinstance(total_cgst_pr, Decimal):
            total_cgst_pr = Decimal(str(total_cgst_pr))
            
        total_sgst_pr = queryset.aggregate(Sum('SGST_PR')).get('SGST_PR__sum') or zero_decimal
        if not isinstance(total_sgst_pr, Decimal):
            total_sgst_pr = Decimal(str(total_sgst_pr))
        

        # Calculate total ITC from all records (last section)
        total_igst_2b = queryset.aggregate(Sum('IGST_2B')).get('IGST_2B__sum') or zero_decimal
        if not isinstance(total_igst_2b, Decimal):
            total_igst_2b = Decimal(str(total_igst_2b))
            
        total_cgst_2b = queryset.aggregate(Sum('CGST_2B')).get('CGST_2B__sum') or zero_decimal
        if not isinstance(total_cgst_2b, Decimal):
            total_cgst_2b = Decimal(str(total_cgst_2b))
            
        total_sgst_2b = queryset.aggregate(Sum('SGST_2B')).get('SGST_2B__sum') or zero_decimal
        if not isinstance(total_sgst_2b, Decimal):
            total_sgst_2b = Decimal(str(total_sgst_2b))

        

        # Function to safely convert aggregated value to Decimal
        def safe_decimal(value):
            if value is None:
                return zero_decimal
            if not isinstance(value, Decimal):
                return Decimal(str(value))
            return value
        
        # Calculate for B2B Missing in PR
        b2b_missing_in_pr_igst = safe_decimal(queryset.filter(Category='Missing in PR', Document_Type='Regular').aggregate(Sum('IGST_2B')).get('IGST_2B__sum'))
        b2b_missing_in_pr_cgst = safe_decimal(queryset.filter(Category='Missing in PR', Document_Type='Regular').aggregate(Sum('CGST_2B')).get('CGST_2B__sum'))
        b2b_missing_in_pr_sgst = safe_decimal(queryset.filter(Category='Missing in PR', Document_Type='Regular').aggregate(Sum('SGST_2B')).get('SGST_2B__sum'))
        
        # Calculate for B2B Missing in 2B
        b2b_missing_in_2b_igst = safe_decimal(queryset.filter(Category='Missing in 2B', Document_Type='Regular').aggregate(Sum('IGST_PR')).get('IGST_PR__sum'))
        b2b_missing_in_2b_cgst = safe_decimal(queryset.filter(Category='Missing in 2B', Document_Type='Regular').aggregate(Sum('CGST_PR')).get('CGST_PR__sum'))
        b2b_missing_in_2b_sgst = safe_decimal(queryset.filter(Category='Missing in 2B', Document_Type='Regular').aggregate(Sum('SGST_PR')).get('SGST_PR__sum'))

        # Calculate for B2B Value Mismatch
        b2b_value_mismatch_igst = safe_decimal(queryset.filter(Category='Value Mismatch', Document_Type='Regular').aggregate(Sum('IGST_difference')).get('IGST_difference__sum'))
        b2b_value_mismatch_cgst = safe_decimal(queryset.filter(Category='Value Mismatch', Document_Type='Regular').aggregate(Sum('CGST_difference')).get('CGST_difference__sum'))
        b2b_value_mismatch_sgst = safe_decimal(queryset.filter(Category='Value Mismatch', Document_Type='Regular').aggregate(Sum('SGST_difference')).get('SGST_difference__sum'))

        
        # Calculate for Credit Notes Missing in PR
        cn_missing_in_pr_igst = safe_decimal(queryset.filter(Category='Missing in PR', Document_Type='Credit Note').aggregate(Sum('IGST_2B')).get('IGST_2B__sum'))
        cn_missing_in_pr_cgst = safe_decimal(queryset.filter(Category='Missing in PR', Document_Type='Credit Note').aggregate(Sum('CGST_2B')).get('CGST_2B__sum'))
        cn_missing_in_pr_sgst = safe_decimal(queryset.filter(Category='Missing in PR', Document_Type='Credit Note').aggregate(Sum('SGST_2B')).get('SGST_2B__sum'))
        
        # Calculate for Credit Notes Missing in 2B
        cn_missing_in_2b_igst = safe_decimal(queryset.filter(Category='Missing in 2B', Document_Type='Credit Note').aggregate(Sum('IGST_PR')).get('IGST_PR__sum'))
        cn_missing_in_2b_cgst = safe_decimal(queryset.filter(Category='Missing in 2B', Document_Type='Credit Note').aggregate(Sum('CGST_PR')).get('CGST_PR__sum'))
        cn_missing_in_2b_sgst = safe_decimal(queryset.filter(Category='Missing in 2B', Document_Type='Credit Note').aggregate(Sum('SGST_PR')).get('SGST_PR__sum'))

        # Calculate for Credit Note Value Mismatch
        cn_value_mismatch_igst = safe_decimal(queryset.filter(Category='Value Mismatch', Document_Type='Credit Note').aggregate(Sum('IGST_difference')).get('IGST_difference__sum'))
        cn_value_mismatch_cgst = safe_decimal(queryset.filter(Category='Value Mismatch', Document_Type='Credit Note').aggregate(Sum('CGST_difference')).get('CGST_difference__sum'))
        cn_value_mismatch_sgst = safe_decimal(queryset.filter(Category='Value Mismatch', Document_Type='Credit Note').aggregate(Sum('SGST_difference')).get('SGST_difference__sum'))
        
        # Calculate for Debit Notes Missing in PR
        dn_missing_in_pr_igst = safe_decimal(queryset.filter(Category='Missing in PR', Document_Type='Debit Note').aggregate(Sum('IGST_2B')).get('IGST_2B__sum'))
        dn_missing_in_pr_cgst = safe_decimal(queryset.filter(Category='Missing in PR', Document_Type='Debit Note').aggregate(Sum('CGST_2B')).get('CGST_2B__sum'))
        dn_missing_in_pr_sgst = safe_decimal(queryset.filter(Category='Missing in PR', Document_Type='Debit Note').aggregate(Sum('SGST_2B')).get('SGST_2B__sum'))
        
        # Calculate for Debit Notes Missing in 2B
        dn_missing_in_2b_igst = safe_decimal(queryset.filter(Category='Missing in 2B', Document_Type='Debit Note').aggregate(Sum('IGST_PR')).get('IGST_PR__sum'))
        dn_missing_in_2b_cgst = safe_decimal(queryset.filter(Category='Missing in 2B', Document_Type='Debit Note').aggregate(Sum('CGST_PR')).get('CGST_PR__sum'))
        dn_missing_in_2b_sgst = safe_decimal(queryset.filter(Category='Missing in 2B', Document_Type='Debit Note').aggregate(Sum('SGST_PR')).get('SGST_PR__sum'))

        # Calculate for Debit Note Value Mismatch
        dn_value_mismatch_igst = safe_decimal(queryset.filter(Category='Value Mismatch', Document_Type='Debit Note').aggregate(Sum('IGST_difference')).get('IGST_difference__sum'))
        dn_value_mismatch_cgst = safe_decimal(queryset.filter(Category='Value Mismatch', Document_Type='Debit Note').aggregate(Sum('CGST_difference')).get('CGST_difference__sum'))
        dn_value_mismatch_sgst = safe_decimal(queryset.filter(Category='Value Mismatch', Document_Type='Debit Note').aggregate(Sum('SGST_difference')).get('SGST_difference__sum'))
        

        total_itc_pr = total_igst_pr + total_cgst_pr + total_sgst_pr
        total_itc_2b = total_igst_2b + total_cgst_2b + total_sgst_2b

        # Assign signs to value mismatches
        sign = -1 if total_itc_pr > total_itc_2b else 1

        if b2b_value_mismatch_igst != 0:
            b2b_value_mismatch_igst = abs(b2b_value_mismatch_igst) * sign
        if b2b_value_mismatch_cgst != 0:
            b2b_value_mismatch_cgst = abs(b2b_value_mismatch_cgst) * sign
        if b2b_value_mismatch_sgst != 0:
            b2b_value_mismatch_sgst = abs(b2b_value_mismatch_sgst) * sign

        if cn_value_mismatch_igst != 0:
            cn_value_mismatch_igst = abs(cn_value_mismatch_igst) * sign
        if cn_value_mismatch_cgst != 0:
            cn_value_mismatch_cgst = abs(cn_value_mismatch_cgst) * sign
        if cn_value_mismatch_sgst != 0:
            cn_value_mismatch_sgst = abs(cn_value_mismatch_sgst) * sign

        if dn_value_mismatch_igst != 0:
            dn_value_mismatch_igst = abs(dn_value_mismatch_igst) * sign
        if dn_value_mismatch_cgst != 0:
            dn_value_mismatch_cgst = abs(dn_value_mismatch_cgst) * sign
        if dn_value_mismatch_sgst != 0:
            dn_value_mismatch_sgst = abs(dn_value_mismatch_sgst) * sign



        # Calculate subtotal (sum of all 6 rows)
        subtotal_igst = (abs(b2b_missing_in_pr_igst) - abs(b2b_missing_in_2b_igst) - abs(cn_missing_in_pr_igst) + abs(cn_missing_in_2b_igst) + abs(dn_missing_in_pr_igst) - abs(dn_missing_in_2b_igst) + b2b_value_mismatch_igst + cn_value_mismatch_igst + dn_value_mismatch_igst)

        subtotal_cgst = (abs(b2b_missing_in_pr_cgst) - abs(b2b_missing_in_2b_cgst) - abs(cn_missing_in_pr_cgst) + abs(cn_missing_in_2b_cgst) + abs(dn_missing_in_pr_cgst) - abs(dn_missing_in_2b_cgst) + b2b_value_mismatch_cgst + cn_value_mismatch_cgst + dn_value_mismatch_cgst)

        subtotal_sgst = (abs(b2b_missing_in_pr_sgst) - abs(b2b_missing_in_2b_sgst) - abs(cn_missing_in_pr_sgst) + abs(cn_missing_in_2b_sgst) + abs(dn_missing_in_pr_sgst) - abs(dn_missing_in_2b_sgst) + b2b_value_mismatch_sgst + cn_value_mismatch_sgst + dn_value_mismatch_sgst)

               
        # Helper function to convert Decimal to float with 2 decimal places
        def to_float(dec):
            return float(dec.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        
        # Create the response data structure with float values rounded to 2 decimal places
        def to_negative_if_value(val):
            val = to_float(val)
            return -val if val != 0 else 0.0

        return [
            {
                "document_type": "",
                "reconciliation_breakup_summary": "Net ITC as per Books (ITC in B2B/invoices + ITC Debit notes - ITC in Credit notes)",
                "igst": to_float(total_igst_pr),
                "cgst": to_float(total_cgst_pr),
                "sgst": to_float(total_sgst_pr),
                "total": round(
                            to_float(total_igst_pr) + 
                            to_float(total_cgst_pr) + 
                            to_float(total_sgst_pr), 2
                        )
            },
            {
                "document_type": "Purchases B2B", # add missing in pr
                "reconciliation_breakup_summary": "Present in 2B But NOT in Books",
                "igst": to_float(abs(b2b_missing_in_pr_igst)),
                "cgst": to_float(abs(b2b_missing_in_pr_cgst)),
                "sgst": to_float(abs(b2b_missing_in_pr_sgst)),
                "total": round(
                            to_float(abs(b2b_missing_in_pr_igst)) + 
                            to_float(abs(b2b_missing_in_pr_cgst)) + 
                            to_float(abs(b2b_missing_in_pr_sgst)), 2
                        )
            },
            {
                "document_type": "Purchases B2B", # subtract missing in 2b
                "reconciliation_breakup_summary": "Present in Books But NOT in 2B",
                "igst": to_negative_if_value(abs(b2b_missing_in_2b_igst)),
                "cgst": to_negative_if_value(abs(b2b_missing_in_2b_cgst)),
                "sgst": to_negative_if_value(abs(b2b_missing_in_2b_sgst)),
                "total": round(
                            to_negative_if_value(abs(b2b_missing_in_2b_igst)) + 
                            to_negative_if_value(abs(b2b_missing_in_2b_cgst)) + 
                            to_negative_if_value(abs(b2b_missing_in_2b_sgst)), 2
                        )
            },
            {
                "document_type": "Purchases B2B", # vm depends on itc diff
                "reconciliation_breakup_summary": "Value Mismatch between Books and 2B",
                "igst": to_float(b2b_value_mismatch_igst),
                "cgst": to_float(b2b_value_mismatch_cgst),
                "sgst": to_float(b2b_value_mismatch_sgst),
                "total" : round(
                            to_float(b2b_value_mismatch_igst) +
                            to_float(b2b_value_mismatch_cgst) + 
                            to_float(b2b_value_mismatch_sgst), 2
                        )
            },
            {
                "document_type": "Credit Notes", # subtract missing in pr
                "reconciliation_breakup_summary": "Present in 2B But NOT in Books",
                "igst": to_negative_if_value(abs(cn_missing_in_pr_igst)),
                "cgst": to_negative_if_value(abs(cn_missing_in_pr_cgst)),
                "sgst": to_negative_if_value(abs(cn_missing_in_pr_sgst)),
                "total": round(
                            to_negative_if_value(abs(cn_missing_in_pr_igst)) +
                            to_negative_if_value(abs(cn_missing_in_pr_cgst)) +
                            to_negative_if_value(abs(cn_missing_in_pr_sgst)), 2
                        )
            },
            {
                "document_type": "Credit Notes", # add missing in 2b
                "reconciliation_breakup_summary": "Present in Books But NOT in 2B",
                "igst": to_float(abs(cn_missing_in_2b_igst)),
                "cgst": to_float(abs(cn_missing_in_2b_cgst)),
                "sgst": to_float(abs(cn_missing_in_2b_sgst)),
                "total": round(
                            to_float(abs(cn_missing_in_2b_igst)) +
                            to_float(abs(cn_missing_in_2b_cgst)) +
                            to_float(abs(cn_missing_in_2b_sgst)), 2
                        )
            },
            {
                "document_type": "Credit Notes", # depends on itc difference
                "reconciliation_breakup_summary": "Value Mismatch between Books and 2B",
                "igst": to_float(cn_value_mismatch_igst),
                "cgst": to_float(cn_value_mismatch_cgst),
                "sgst": to_float(cn_value_mismatch_sgst),
                "total": round(
                            to_float(cn_value_mismatch_igst) +
                            to_float(cn_value_mismatch_cgst) +
                            to_float(cn_value_mismatch_sgst), 2
                        )
            },
            {
                "document_type": "Debit Notes", # add missing in pr
                "reconciliation_breakup_summary": "Present in 2B But NOT in Books",
                "igst": to_float(abs(dn_missing_in_pr_igst)),
                "cgst": to_float(abs(dn_missing_in_pr_cgst)),
                "sgst": to_float(abs(dn_missing_in_pr_sgst)),
                "total": round(
                            to_float(abs(dn_missing_in_pr_igst)) +
                            to_float(abs(dn_missing_in_pr_cgst)) +
                            to_float(abs(dn_missing_in_pr_sgst)), 2
                        )
            },
            {
                "document_type": "Debit Notes", # subtract missing in 2b
                "reconciliation_breakup_summary": "Present in 2B But NOT in Books",
                "igst": to_float(abs(dn_missing_in_pr_igst)),
                "cgst": to_float(abs(dn_missing_in_pr_cgst)),
                "sgst": to_float(abs(dn_missing_in_pr_sgst)),
                "total": round(
                            to_float(abs(dn_missing_in_pr_igst)) +
                            to_float(abs(dn_missing_in_pr_cgst)) +
                            to_float(abs(dn_missing_in_pr_sgst)), 2
                        )
            },
            {
                "document_type": "Debit Notes", # value mismatch depends on itc difference
                "reconciliation_breakup_summary": "Value Mismatch between Books and 2B",
                "igst": to_float(dn_missing_in_2b_igst),
                "cgst": to_float(dn_missing_in_2b_cgst),
                "sgst": to_float(dn_missing_in_2b_sgst),
                "total": round(
                            to_float(dn_missing_in_2b_igst) +
                            to_float(dn_missing_in_2b_cgst) +
                            to_float(dn_missing_in_2b_sgst), 2
                        )
            },
            {
                "document_type": "",
                "reconciliation_breakup_summary": "",
                "igst": to_float(subtotal_igst),
                "cgst": to_float(subtotal_cgst),
                "sgst": to_float(subtotal_sgst),
                "total": round(
                            to_float(subtotal_igst) +
                            to_float(subtotal_cgst) +
                            to_float(subtotal_sgst), 2
                        )
            },
            {
                "document_type": "",
                "reconciliation_breakup_summary": "Net ITC as per 2B (ITC in B2B/invoices + ITC Debit notes - ITC in Credit notes)",
                "igst": to_float(total_igst_2b),
                "cgst": to_float(total_cgst_2b),
                "sgst": to_float(total_sgst_2b),
                "total": round(
                            to_float(total_igst_2b) +
                            to_float(total_cgst_2b) +
                            to_float(total_sgst_2b), 2
                        )
            }
        ]

class TimeRangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeRange
        fields = [
            "Month",
            "Year",
            "Quarter",
            "FY",
            "status_PR",
            "status_2B",
            "status_reco",
            "status_upload",
            "no_of_doc_PR",
            "no_of_doc_2B",
            "tax_difference",
            "itc_PR",
            "itc_2B",
        ]
    
class HistorySerializer(serializers.ModelSerializer):
    basic_details = serializers.SerializerMethodField()
    invoice_details = serializers.SerializerMethodField()
    invoice_date = serializers.SerializerMethodField()
    GSTIN = serializers.SerializerMethodField()
    taxable_value = serializers.SerializerMethodField()
    tax_value = serializers.SerializerMethodField()
    total_value = serializers.SerializerMethodField()
    time_period = serializers.SerializerMethodField()
    
    class Meta:
        model = ReconciliationReport
        fields = [
            'id', 'basic_details', 'invoice_details', 'invoice_date', 'GSTIN',
            'taxable_value', 'tax_value', 'total_value', 'time_period'
        ]

    
    def get_basic_details(self, obj):
        user = obj.user  
        ist = timezone('Asia/Kolkata')
        ist_time = obj.created_at.astimezone(ist)
        return {
            "date": ist_time.strftime("%d-%m-%Y"),
            "time": ist_time.strftime("%H:%M:%S"),
            "user": user.first_name if user else "Unknown"
        }
    
    def get_invoice_details(self, obj):
        return {
            "2B": obj.Supplier_Invoice_Number_2B or obj.Supplier_Note_Number_2B,
            "PR": obj.Supplier_Invoice_Number_PR or obj.Supplier_Note_Number_PR
        }
    
    def get_invoice_date(self, obj):
        return {
            "2B": format_date(obj.Supplier_Invoice_Date_2B or obj.Supplier_Note_Date_2B),
            "PR": format_date(obj.Supplier_Invoice_Date_PR or obj.Supplier_Note_Date_PR)
        }
    
    def get_GSTIN(self, obj):
        return {
            "2B": obj.GSTIN_of_Supplier_2B,
            "PR": obj.GSTIN_of_Supplier_PR
        }
    
    def get_taxable_value(self, obj):
        return {
            "2B": obj.Taxable_Value_2B,
            "PR": obj.Taxable_Value_PR
        }
    
    def get_tax_value(self, obj):
        return {
            "2B": obj.Total_tax_2B,
            "PR": obj.Total_tax_PR,
            "tax_difference": obj.Total_Tax_Difference
        }
    
    def get_total_value(self, obj):
        total_2B = (float(obj.Taxable_Value_2B) if obj.Taxable_Value_2B else 0) + (float(obj.Total_tax_2B) if obj.Total_tax_2B else 0)
        total_PR = (float(obj.Taxable_Value_PR) if obj.Taxable_Value_PR else 0) + (float(obj.Total_tax_PR) if obj.Total_tax_PR else 0)
        return {
            "2B": total_2B,
            "PR": total_PR
        }
    
    def get_time_period(self, obj):
        return {
            "2B": self.format_period(obj.Period_2B),
            "PR": self.format_period(obj.Period_PR)
        }
    
    def format_period(self, period):
        if period:
            month, year = period[:-4], period[-4:] if len(period) > 4 else (period[:-3], period[-3:])
            month_names = {
                "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "Jun",
                "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"
            }
            return f"{month_names.get(month.zfill(2), 'Unknown')} {year}"
        return ""

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeRange
        fields = ['id', 'Month', 'Year', 'FY', 'status_PR', 'status_2B','status_reco']

class NotificationSerializer(serializers.ModelSerializer):
    # Core fields directly from the model
    # Convert ID to string as it's often UUID or needs to match frontend's string expectation
    id = serializers.CharField() # Django's default .id handles UUID/int correctly, CharField converts it to string

    module = serializers.CharField()
    title = serializers.CharField()
    message = serializers.CharField()
    type = serializers.CharField()
    priority = serializers.CharField()
    read = serializers.BooleanField()

    # Timestamps need specific formatting (ISO 8601 with 'Z')
    timestamp = serializers.DateTimeField(format=None) # Start with Django's default ISO 8601, then customize
    expires_at = serializers.DateTimeField(allow_null=True, required=False, format=None)

    # Nested/Custom fields
    context = serializers.SerializerMethodField()
    metadata = serializers.JSONField(binary=False, allow_null=True) # binary=False for human-readable JSON
    actions = serializers.SerializerMethodField()

    # thread_id might be blank/null, ensure it's an empty string if null for consistency with WS format
    thread_id = serializers.CharField(allow_null=True, required=False)

    class Meta:
        model = Notifications
        fields = [
            'id', 'module', 'title', 'message', 'type', 'priority',
            'context', 'metadata', 'timestamp', 'read', 'expires_at',
            'actions', 'thread_id'
        ]

    # --- Methods to mimic the structure of to_websocket_format() ---

    def get_context(self, obj):
        """
        Populates the 'context' field based on related models, mirroring the WebSocket format.
        """
        gstin_details = {
            "gstin": obj.user_gst_info.gstin if obj.user_gst_info else None,
            "name": obj.user_gst_info.company_name if obj.user_gst_info else None
        }
        # Based on previous discussion, company_id_val was hardcoded to "" in to_websocket_format
        company_id_val = "" 
        user_id_val = str(obj.user.id) # Ensure user ID is a string

        return {
            "gstin_details": gstin_details,
            "company_id": company_id_val,
            "user_id": user_id_val
        }

    def get_actions(self, obj):
        """
        Populates the 'actions' field, mirroring the WebSocket format.
        Ensures empty string for null fields as per common frontend expectation.
        """
        return {
            "type": obj.action_type if obj.action_type is not None else "",
            "label": obj.action_label if obj.action_label is not None else "",
            "url": obj.action_url if obj.action_url is not None else "",
            "app": obj.action_app if obj.action_app is not None else ""
        }

    def to_representation(self, instance):
        """
        Overrides the default representation to apply specific formatting like ISO date and
        handle nulls for thread_id and metadata to match the exact WebSocket payload structure.
        """
        ret = super().to_representation(instance)

        # Apply specific ISO format with 'Z' suffix for timestamps
        if ret['timestamp']:
            ret['timestamp'] = instance.timestamp.isoformat().replace('+00:00', 'Z')
        if ret['expires_at']:
            ret['expires_at'] = instance.expires_at.isoformat().replace('+00:00', 'Z')
        
        # Ensure thread_id is an empty string if it's None/null in the DB
        if ret['thread_id'] is None:
            ret['thread_id'] = ""
        
        # Ensure metadata is an empty dictionary if it's None/null in the DB
        if ret['metadata'] is None:
            ret['metadata'] = {}

        return ret