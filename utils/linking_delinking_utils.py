import pandas as pd
from decimal import Decimal

from apps.gst.models import ReconciliationReport, UserModificationHistory
from apps.gst.utils.date_formatting_utils import calculateFY

def assign_rank(row, key_data):
    # Condition 1: 2 Identifiers Match & Value Fields Match (Rank 2)
    identifiers = [
        row["supplier_gstin"],
        row["document_number"],
        row["document_date"],
    ]

    key_identifiers = [
        key_data["supplier_gstin"],
        key_data["document_number"],
        key_data["document_date"],
    ]

    value_fields = ["invoice_value", "taxable_value", "igst", "cgst", "sgst"]

    identifier_match_count = sum(
        1 for i in range(3) if identifiers[i] == key_identifiers[i]
    )

    # values_match = all(abs(float(row[field]) - float(key_data[field])) <= 2 for field in value_fields)

    # try:
    values_match = all(
        abs(Decimal(str(row.get(field, 0))) - Decimal(str(key_data.get(field, 0))))
        <= Decimal("2")
        for field in value_fields
    )
    # except (InvalidOperation, TypeError):
    #     values_match = False

    if identifier_match_count == 2 and values_match:
        return 2

    # Condition 2: GSTIN Mismatch but Same PAN, Other Fields Match (Rank 1)
    if (
        row["supplier_gstin"][2:12] == key_data["supplier_gstin"][2:12]
        and row["document_number"]
        == key_data["document_number"]
        and row["document_date"]
        == key_data["document_date"]
        and values_match
    ):
        return 1

    # Condition 3: Invoice Number Mismatch but Jumbled (Same Vendor) (Rank 4)
    if (
        sorted(str(row["document_number"]))
        == sorted(str(key_data["document_number"]))
        and row["document_date"]
        == key_data["document_date"]
        and row["supplier_gstin"] == key_data["supplier_gstin"]
        and values_match
    ):
        return 4

    # Condition 4: Invoice Date Mismatch but Exact Invoice Number (Rank 3)
    if (
        row["document_number"]
        == key_data["document_number"]
        and row["document_date"]
        != key_data["document_date"]
        and values_match
    ):
        return 3

    # Condition 5: Invoice Date & Invoice Number Mismatch but All Values Match (Rank 5)
    if values_match and row["supplier_gstin"] == key_data["supplier_gstin"]:
        return 5

    # Condition 6: Completely Different Vendor but All Values Match (Rank 6)
    if row["supplier_gstin"] != key_data["supplier_gstin"] and values_match:
        return 6

    # Condition 7: Same Vendor every other that doesnt fall under above ranks
    if row["supplier_gstin"] == key_data["supplier_gstin"]:
        return 7

    # Condition 8: None of the Above (Rank 7)
    return 8


def add_transaction_into_reco_table(
    pr_data_df, data2b_df, user_id, user_gst_in_id, Category
):

    def preprocess_data(pr_data_df, data2b_df):
        for df in [pr_data_df, data2b_df]:
            if "total_tax" not in df.columns:
                df["total_tax"] = df[["cgst", "sgst", "igst"]].sum(axis=1).fillna(0)

    preprocess_data(pr_data_df, data2b_df)

    def add_to_globalDF(
        row_pr, row_2b, category, user_id, user_gst_number
    ):

        def get_reason_for_categorization(category):
            if category == "Match":
                return ""
            elif category == "Missing in 2B":
                return "Not found in 2B"
            elif category == "Missing in PR":
                return "Not found in PR"
            elif category == "Value Mismatch":
                return "Mismatch in Taxable Value, Invoice Value, IGST, CGST, or SGST."
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
            link_status="linked",
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


        user_modification_entry = UserModificationHistory(
            GSTIN_of_User=reconciliation_entry.GSTIN_of_User,
            GSTIN_of_Supplier_2B=reconciliation_entry.GSTIN_of_Supplier_2B,
            GSTIN_of_Supplier_PR=reconciliation_entry.GSTIN_of_Supplier_PR,
            Supplier_Invoice_Number_2B=reconciliation_entry.Supplier_Invoice_Number_2B,
            Supplier_Invoice_Number_PR=reconciliation_entry.Supplier_Invoice_Number_PR,
            Supplier_Invoice_Date_2B=reconciliation_entry.Supplier_Invoice_Date_2B,
            Supplier_Invoice_Date_PR=reconciliation_entry.Supplier_Invoice_Date_PR,
            Supplier_Note_Number_2B=reconciliation_entry.Supplier_Note_Number_2B,
            Supplier_Note_Number_PR=reconciliation_entry.Supplier_Note_Number_PR,
            Supplier_Note_Date_2B=reconciliation_entry.Supplier_Note_Date_2B,
            Supplier_Note_Date_PR=reconciliation_entry.Supplier_Note_Date_PR,
            Category=reconciliation_entry.Category,
            Document_Type=reconciliation_entry.Document_Type,
            Section=reconciliation_entry.Section,
            FY_of_Invoice_PR=reconciliation_entry.FY_of_Invoice_PR,
            FY_of_Invoice_2B=reconciliation_entry.FY_of_Invoice_2B,
            Period_PR=reconciliation_entry.Period_PR,
            Period_2B=reconciliation_entry.Period_2B,
            Name_of_Supplier_2B=reconciliation_entry.Name_of_Supplier_2B,
            Name_of_Supplier_PR=reconciliation_entry.Name_of_Supplier_PR,
            Place_of_Supply_PR=reconciliation_entry.Place_of_Supply_PR,
            Place_of_Supply_2B=reconciliation_entry.Place_of_Supply_2B,
            Invoice_Value_PR=reconciliation_entry.Invoice_Value_PR,
            Invoice_Value_2B=reconciliation_entry.Invoice_Value_2B,
            Invoice_Value_Difference=reconciliation_entry.Invoice_Value_Difference,
            Taxable_Value_PR=reconciliation_entry.Taxable_Value_PR,
            Taxable_Value_2B=reconciliation_entry.Taxable_Value_2B,
            Taxable_Value_Difference=reconciliation_entry.Taxable_Value_Difference,
            IGST_PR=reconciliation_entry.IGST_PR,
            IGST_2B=reconciliation_entry.IGST_2B,
            IGST_difference=reconciliation_entry.IGST_difference,
            CGST_PR=reconciliation_entry.CGST_PR,
            CGST_2B=reconciliation_entry.CGST_2B,
            CGST_difference=reconciliation_entry.CGST_difference,
            SGST_PR=reconciliation_entry.SGST_PR,
            SGST_2B=reconciliation_entry.SGST_2B,
            SGST_difference=reconciliation_entry.SGST_difference,
            Cess_PR=reconciliation_entry.Cess_PR,
            Cess_2B=reconciliation_entry.Cess_2B,
            Total_tax_PR=reconciliation_entry.Total_tax_PR,
            Total_tax_2B=reconciliation_entry.Total_tax_2B,
            Total_Tax_Difference=reconciliation_entry.Total_Tax_Difference,
            ITC_Availability_2B=reconciliation_entry.ITC_Availability_2B,
            Reason=reconciliation_entry.Reason,
            Warning=reconciliation_entry.Warning,
            Supply_attract_reverse_charge_2B=reconciliation_entry.Supply_attract_reverse_charge_2B,
            Reason_for_Categorization=reconciliation_entry.Reason_for_Categorization,
            User_Comments=None,
            Last_Action_Taken=None,
            Timestamp_of_Last_Action=None,
            User_Identification=None,
            Inter_or_Intra_2B=reconciliation_entry.Inter_or_Intra_2B,
            Transaction_id_pr=reconciliation_entry.Transaction_id_pr,
            Transaction_id_2b=reconciliation_entry.Transaction_id_2b,
            user_id=user_id,
            user_gstin_id=user_gst_in_id,
            link_status="linked",
            link_range=reconciliation_entry.link_range
        )
        user_modification_entry.save()

    for _, row_pr in pr_data_df.iterrows():
        for _, row_2b in data2b_df.iterrows():

            result = add_to_globalDF(row_pr, row_2b, Category, user_id, user_gst_in_id)

    # print("data added into db:", result)
    # print("Added Linked Invoice to DB")
