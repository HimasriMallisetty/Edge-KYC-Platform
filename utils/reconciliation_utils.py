import pandas as pd
from rapidfuzz import fuzz

from decimal import Decimal

from django.db.models.functions import Coalesce
from django.db.models import Q, Sum, F, Value, DecimalField


from apps.gst.models import (
    ReconciliationReport, 
    TimeRange, 
    PrData
)

from apps.gst.utils.notification_socket_utils import (
    send_websocket_notification_sync
)

from apps.gst.utils.date_formatting_utils import (
    extract_month_year,
    calculateFY,
    get_return_periods
)

from apps.gst.constants import *
from apps.core.sandbox import *
from apps.gst.models import Data2B, ReconciliationReport



basic_string_criteria = {
    "supplier_gstin": 100,
    "document_number": 100,
    "document_date": 100,
    "document_type": 100,
}
basic_numeric_criteria = {
    "taxable_value": 2,
    "sgst": 2,
    "cgst": 2,
    "igst": 2,
    "invoice_value": 2,
}
value_mismatch_numeric_criteria = {
    "taxable_value": 2,
    "sgst": 2,
    "cgst": 2,
    "igst": 2,
    "invoice_value": 2,
}


class DataProcessor:
    def __init__(self, financial_year, df_2B, df_PR, user_id, user_gst_number):
        self.df_2B = df_2B
        self.df_PR = df_PR
        self.financial_year = financial_year
        self.user_id = user_id
        self.user_gst_number = user_gst_number
        self.named_dfs = {}

    # Adding Total Tax
    def preprocess_data(self):
        for df in [self.df_2B, self.df_PR]:
            if "total_tax" not in df.columns:
                df["total_tax"] = df[["cgst", "sgst", "igst"]].sum(axis=1).fillna(0)

    # Logic For Comparision or Main Reconciliation Linking Logic.
    def compare_rows(self, row1, row2, string_criteria, numeric_criteria):
        string_match = all(
            fuzz.ratio(str(row1[col]), str(row2[col])) >= threshold
            for col, threshold in string_criteria.items()
        )
        numeric_match = all(
            abs(row1[col] - row2[col]) <= threshold
            for col, threshold in numeric_criteria.items()
        )
        return string_match and numeric_match

    def compare_rows_modified_not_in_use(
        self, row1, row2, string_criteria, numeric_criteria
    ):
        string_match = True

        for col, threshold in string_criteria.items():
            if col == "document_date":
                # Extract Month-Year instead of full date comparison
                date1 = extract_month_year(str(row1[col]))
                date2 = extract_month_year(str(row2[col]))

                if date1 is None or date2 is None:
                    string_match = False
                elif (
                    date1 != date2
                ):  # Direct comparison since we only need exact match on month-year
                    string_match = False
            else:
                # Apply fuzzy matching for other string columns
                if fuzz.ratio(str(row1[col]), str(row2[col])) < threshold:
                    string_match = False

        numeric_match = all(
            abs(row1[col] - row2[col]) <= threshold
            for col, threshold in numeric_criteria.items()
        )

        return string_match and numeric_match

    def compare_rows_value_mismatch(
        self, row1, row2, string_criteria, numeric_criteria
    ):
        string_match = all(
            fuzz.ratio(str(row1[col]), str(row2[col])) >= threshold
            for col, threshold in string_criteria.items()
        )
        numeric_mismatch = any(
            abs(row1[col] - row2[col]) > threshold
            for col, threshold in numeric_criteria.items()
        )
        return string_match and numeric_mismatch

    def compare_rows_value_mismatch_modified_not_in_use(
        self, row1, row2, string_criteria, numeric_criteria
    ):
        string_match = True

        for col, threshold in string_criteria.items():
            if col == "document_date":
                date1 = extract_month_year(str(row1[col]))
                date2 = extract_month_year(str(row2[col]))

                if date1 is None or date2 is None:
                    string_match = False
                elif date1 != date2:
                    string_match = False
            else:
                if fuzz.ratio(str(row1[col]), str(row2[col])) < threshold:
                    string_match = False

        numeric_mismatch = any(
            abs(row1[col] - row2[col]) > threshold
            for col, threshold in numeric_criteria.items()
        )

        return string_match and numeric_mismatch

    def categorize_record(self, row1, row2):
        if self.compare_rows(row1, row2, basic_string_criteria, basic_numeric_criteria):
            return "Match"
        elif self.compare_rows_value_mismatch(
            row1, row2, basic_string_criteria, value_mismatch_numeric_criteria
        ):
            return "Value Mismatch"
        return None

    def match_dataframes(self, financial_year, user_id, user_gst_number):
        matched_2B = set()

        for i, row_pr in self.df_PR.iterrows():
            match_found = False

            for j, row_2b in self.df_2B.iterrows():
                category = self.categorize_record(row_pr, row_2b)
                if category:
                    match_found = True
                    matched_2B.add(j)
                    self.add_to_globalDF(
                        row_pr,
                        row_2b,
                        category,
                        financial_year,
                        user_id,
                        user_gst_number,
                    )
                    break

            if not match_found:
                self.add_to_globalDF(
                    row_pr,
                    None,
                    "Missing in 2B",
                    financial_year,
                    user_id,
                    user_gst_number,
                )

        for j, row_2b in self.df_2B.iterrows():
            if j not in matched_2B:
                self.add_to_globalDF(
                    None,
                    row_2b,
                    "Missing in PR",
                    financial_year,
                    user_id,
                    user_gst_number,
                )

    def add_to_globalDF(
        self, row_pr, row_2b, category, financial_year, user_id, user_gst_number
    ):

        def get_reason_for_categorization(category):
            if category == "Match":
                return ""
            elif category == "Missing in 2B":
                return "Not found in 2B"
            elif category == "Missing in PR":
                return "Not found in PR"
            elif category == "Value Mismatch":
                return "Mismatch in Taxable Value, Invoice Value, igst, cgst, or sgst."
            else:
                return None

        def get_warning(itc_availability_2b, total_tax_2b):
            if itc_availability_2b == "N" and total_tax_2b == 0.00:
                # print("in this")
                return "ITC is ineligible as per 2B"
            return None

        if row_2b is not None:
            invCondition = row_2b.get("section", "") in ["b2b", "b2ba"] or (
                row_2b.get("section", "") == ""
                and row_pr is not None
                and row_pr.get("document_type", "") == "Regular"
            )
        else:
            invCondition = (
                row_pr is not None and row_pr.get("document_type", "") == "Regular"
            )

        Taxable_Value_PR = row_pr["taxable_value"] if row_pr is not None else 0

        Taxable_Value_2B = row_2b["taxable_value"] if row_2b is not None else 0
        Invoice_Value_PR = row_pr["invoice_value"] if row_pr is not None else 0
        Invoice_Value_2B = row_2b["invoice_value"] if row_2b is not None else 0

        IGST_PR = row_pr["igst"] if row_pr is not None else 0
        IGST_2B = row_2b["igst"] if row_2b is not None else 0

        CGST_PR = row_pr["cgst"] if row_pr is not None else 0
        CGST_2B = row_2b["cgst"] if row_2b is not None else 0

        SGST_PR = row_pr["sgst"] if row_pr is not None else 0
        SGST_2B = row_2b["sgst"] if row_2b is not None else 0
        # SGST_difference = SGST_PR - SGST_2B,

        Cess_PR = (
            row_pr["cess"] if row_pr is not None and pd.notna(row_pr["cess"]) else 0
        )
        Cess_2B = (
            row_2b["cess"] if row_2b is not None and pd.notna(row_2b["cess"]) else 0
        )

        Total_tax_PR = row_pr["total_tax"] if row_pr is not None else 0
        Total_tax_2B = row_2b["total_tax"] if row_2b is not None else 0
        # Total_Tax_Difference = Total_tax_PR - Total_tax_2B,

        return_period_pr = row_pr["return_period"] if row_pr is not None else ""
        return_period_2b = row_2b["return_period"] if row_2b is not None else ""

        reconciliation_entry = ReconciliationReport(
            GSTIN_of_User=(
                row_pr["user_gstin"]
                if row_pr is not None
                else row_2b["user_gstin"]
            ),
            GSTIN_of_Supplier_2B=(
                row_2b["supplier_gstin"] if row_2b is not None else None
            ),
            GSTIN_of_Supplier_PR=(
                row_pr["supplier_gstin"] if row_pr is not None else None
            ),
            Supplier_Invoice_Number_2B=(
                row_2b["document_number"]
                if row_2b is not None and invCondition
                else ""
            ),
            Supplier_Invoice_Number_PR=(
                row_pr["document_number"]
                if row_pr is not None and invCondition
                else ""
            ),
            Supplier_Invoice_Date_2B=(
                row_2b["document_date"]
                if row_2b is not None and invCondition
                else ""
            ),
            Supplier_Invoice_Date_PR=(
                row_pr["document_date"]
                if row_pr is not None and invCondition
                else ""
            ),
            Supplier_Note_Number_2B=(
                row_2b["document_number"]
                if row_2b is not None and not invCondition
                else ""
            ),
            Supplier_Note_Number_PR=(
                row_pr["document_number"]
                if row_pr is not None and not invCondition
                else ""
            ),
            Supplier_Note_Date_2B=(
                row_2b["document_date"]
                if row_2b is not None and not invCondition
                else ""
            ),
            Supplier_Note_Date_PR=(
                row_pr["document_date"]
                if row_pr is not None and not invCondition
                else ""
            ),
            Category=category,
            Document_Type=(
                row_2b["document_type"]
                if row_2b is not None
                else row_pr["document_type"] if row_pr is not None else None
            ),
            Section=row_2b["section"] if row_2b is not None else None,
            FY_of_Invoice_PR=(
                calculateFY(str(row_pr["return_period"]))
                if row_pr is not None
                else None
            ),
            FY_of_Invoice_2B=(
                calculateFY(str(row_2b["return_period"]))
                if row_2b is not None
                else None
            ),
            Period_PR=return_period_pr,
            Period_2B=return_period_2b,
            Name_of_Supplier_2B=(
                row_2b["supplier_name"]
                if row_2b is not None
                else None
            ),
            Name_of_Supplier_PR=(
                row_pr["supplier_name"] if row_pr is not None else None
            ),
            Place_of_Supply_PR=(
                row_pr["place_of_supply"] if row_pr is not None else None
            ),
            Place_of_Supply_2B=(
                row_2b["place_of_supply"] if row_2b is not None else None
            ),
            Invoice_Value_PR=Invoice_Value_PR,
            Invoice_Value_2B=Invoice_Value_2B,
            Invoice_Value_Difference=Invoice_Value_PR - Invoice_Value_2B,
            Taxable_Value_PR=Taxable_Value_PR,
            Taxable_Value_2B=Taxable_Value_2B,
            Taxable_Value_Difference=Taxable_Value_PR - Taxable_Value_2B,
            IGST_PR=IGST_PR,
            IGST_2B=IGST_2B,
            IGST_difference=IGST_PR - IGST_2B,
            CGST_PR=CGST_PR,
            CGST_2B=CGST_2B,
            CGST_difference=CGST_PR - CGST_2B,
            SGST_PR=SGST_PR,
            SGST_2B=SGST_2B,
            SGST_difference=SGST_PR - SGST_2B,
            Cess_PR=Cess_PR,
            Cess_2B=Cess_2B,
            Total_tax_PR=Total_tax_PR,
            Total_tax_2B=Total_tax_2B,
            Total_Tax_Difference=Total_tax_PR - Total_tax_2B,
            ITC_Availability_2B=(
                row_2b["itc_availability"] if row_2b is not None else None
            ),
            Reason=row_2b["itc_unavailability_reason"] if row_2b is not None else None,
            Warning=get_warning(
                row_2b["itc_availability"] if row_2b is not None else None,
                row_2b["total_tax"] if row_2b is not None else None,
            ),
            Supply_attract_reverse_charge_2B=(
                row_2b["supply_attract_reverse_charge"] if row_2b is not None else None
            ),
            Reason_for_Categorization=get_reason_for_categorization(category),
            User_Comments=None,
            Last_Action_Taken=None,
            Timestamp_of_Last_Action=None,
            User_Identification=None,
            Inter_or_Intra_2B=row_2b["inter_or_intra"] if row_2b is not None else None,
            Transaction_id_pr=row_pr["id"] if row_pr is not None else None,
            Transaction_id_2b=row_2b["id"] if row_2b is not None else None,
            user_id=user_id,
            user_gstin_id=user_gst_number,
            link_range=[
                (
                    "Cross Month Match"
                    if category in ["Match", "Value Mismatch"]
                    and int(return_period_pr) != int(return_period_2b)
                    else ""
                )
            ][0],
        )
        reconciliation_entry.save()


def perform_basic_reconciliation(
    data_pr, data_2b, user_id, user_gst_number, financial_year, gst_info
):
    send_websocket_notification_sync(
        user_id=user_id,
        user_gst_info_id=gst_info.id,
        module="reconciliation",
        title=f"Reconciliation Started",
        message=f"Reconciliation for FY {financial_year} has started. We will notify you once it is completed.",
        notification_type="info",
        metadata={"financial_year": financial_year, "status": "started", "record_count": "N/A", "gstin": gst_info.gstin}
    )
    try:
        df_2B = pd.DataFrame(data_2b)
        df_PR = pd.DataFrame(data_pr)
        
        processor = DataProcessor(financial_year, df_2B, df_PR, user_id, user_gst_number)
        processor.preprocess_data()
        processor.match_dataframes(financial_year, user_id, user_gst_number)

        # Updating the status_reco flag in TimeRange API.
        df_PR["accounting_date"] = pd.to_datetime(
            df_PR["accounting_date"], format="%d-%m-%Y"
        )
        unique_month_years = sorted(df_PR["accounting_date"].dt.strftime("%m-%Y").unique())
        unique_month_years = [
            [int(m.split("-")[0]), int(m.split("-")[1])] for m in unique_month_years
        ]

        query = Q()
        for month, year in unique_month_years:
            query |= Q(
                Month=month,
                Year=year,
                user_id=user_id,
                user_gst_info_id=user_gst_number,
            )
        TimeRange.objects.filter(query).update(status_reco=2)

        # Updating reconciliation status in PR and 2B data tables.
        reco_records = ReconciliationReport.objects.filter(
            user_id=user_id, user_gstin_id=user_gst_number
        )

        for record in reco_records:
            # Default to status = 1 (reconciled)
            status = 1

            # If category implies missing, set to 0 (not reconciled)
            if record.Category in ["Missing in PR", "Missing in 2B"]:
                status = 0

            # Update PR record if ID exists
            if record.Transaction_id_pr:
                PrData.objects.filter(id=record.Transaction_id_pr).update(
                    reconciliation_category=record.Category,
                    reconciliation_status=status
                )

            # Update 2B record if ID exists
            if record.Transaction_id_2b:
                Data2B.objects.filter(id=record.Transaction_id_2b).update(
                    reconciliation_category=record.Category,
                    reconciliation_status=status
                )


        def get_financial_year_months(financial_year):
            start_year, end_year = map(int, financial_year.split("-"))
            months = []
            # April to December of start_year
            for month in range(4, 13):
                months.append([month, start_year])

            # January to March of end_year
            for month in range(1, 4):
                months.append([month, end_year])

            return months

        # Computing Aggregates and storing them month wise in TimeRange table for using in Dashboard API
        for month, year in get_financial_year_months(financial_year):
            periods = get_return_periods(financial_year, None, month)

            # Fetching PR Data
            pr_queryset = PrData.objects.filter(
                return_period__in=periods,
                user_id=user_id,
                user_gst_info_id=user_gst_number,
            ).annotate(
                total_tax=Coalesce(F("igst"), Value(0, output_field=DecimalField()))
                + Coalesce(F("cgst"), Value(0, output_field=DecimalField()))
                + Coalesce(F("sgst"), Value(0, output_field=DecimalField()))
            )

            itc_PR = pr_queryset.aggregate(total=Sum("total_tax"))["total"] or Decimal(
                "0.00"
            )
            no_of_doc_PR = pr_queryset.count()

            # Fetching 2B Data
            data2b_queryset = Data2B.objects.filter(
                return_period__in=periods,
                user_id=user_id,
                user_gst_info_id=user_gst_number,
            ).annotate(
                total_tax=Coalesce(F("igst"), Value(0, output_field=DecimalField()))
                + Coalesce(F("cgst"), Value(0, output_field=DecimalField()))
                + Coalesce(F("sgst"), Value(0, output_field=DecimalField()))
            )

            itc_2B = data2b_queryset.aggregate(total=Sum("total_tax"))["total"] or Decimal(
                "0.00"
            )
            no_of_doc_2B = data2b_queryset.count()

            # Tax Difference Calculation
            tax_difference = itc_PR - itc_2B

            # Updating TimeRange Table
            TimeRange.objects.filter(
                Month=month,
                Year=year,
                user_id=user_id,
                user_gst_info_id=user_gst_number,
            ).update(
                itc_2B=itc_2B,
                itc_PR=itc_PR,
                no_of_doc_2B=no_of_doc_2B,
                no_of_doc_PR=no_of_doc_PR,
                tax_difference=tax_difference,
            )
            
        if unique_month_years:
            query = Q()
            for month, year in unique_month_years:
                query |= Q(
                    Month=month,
                    Year=year,
                    user_id=user_id,
                    user_gst_info_id=user_gst_number,
                )
            if query.children:
                TimeRange.objects.filter(query).update(status_reco=2)

        send_websocket_notification_sync(
            user_id=user_id,
            user_gst_info_id=gst_info.id,
            module="reconciliation",
            title=f"Reconciliation Successfully Finished",
            message=f"Reconciliation for FY {financial_year} has been completed successfully.",
            notification_type="success",
            metadata={"financial_year": financial_year, "status": "completed", "record_count": "N/A", "gstin": gst_info.gstin}
        )

        return 200
    
    except Exception as e:
        send_websocket_notification_sync(
            user_id=user_id,
            user_gst_info_id=gst_info.id,
            module="reconciliation",
            title=f"Reconciliation Error",
            message=f"An error occurred during reconciliation for FY {financial_year}. Please try again later.",
            notification_type="error",
            metadata={"financial_year": financial_year, "status": "error", "record_count": "N/A", "gstin": gst_info.gstin}
        )
        print(f"Error in perform_basic_reconciliation: {e}")
        return 500        
