import os
import json
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

from django.db.models import Q
from django_q.tasks import async_task

from apps.core.sandbox import SandboxClient

from apps.gst.constants import (
    COLUMNS_TO_DROP,
    COLUMN_MAPPING,
    NEW_ORDER,
    ADDITIONAL_COLUMNS,
    POS
)
from apps.gst.utils.notification_socket_utils import send_websocket_notification_sync
from apps.gst.utils.date_formatting_utils import get_financial_year_available_months
from apps.gst.models import TimeRange, Data2B




# Load environment variables from .env file
load_dotenv()
SANDBOX_API_KEY = os.getenv("SANDBOX_API_KEY")

def process_json_to_dataframe(data):
    json_data = json.loads(data)

    timestamp = json_data.get("timestamp", "unknown_timestamp")
    try:
        if isinstance(timestamp, int):  # Handle integer timestamp
            gendt = datetime.fromtimestamp(timestamp / 1000).strftime("%Y-%m-%d")
        elif isinstance(timestamp, str):  # Handle string ISO 8601 timestamp
            gendt = datetime.fromisoformat(timestamp.replace("Z", "")).strftime(
                "%Y-%m-%d"
            )
        else:
            gendt = "unknown_date"
    except ValueError:
        gendt = "unknown_date"

    # Navigate to docdata
    level_3_data = json_data.get("data", {}).get("data", {}).get("data", {})
    docdata = level_3_data.get("docdata", {})
    if not isinstance(docdata, dict):
        raise ValueError(
            "The 'docdata' key is missing or not a dictionary in the JSON."
        )

    # Extract metadata
    gstin_of_taxpayer = level_3_data.get("gstin", "unknown_gstin")
    # print("gstin_of_taxpayer", gstin_of_taxpayer)
    rtnprd = level_3_data.get("rtnprd", "unknown_period")

    # Initialize rows
    rows = []

    # Function to process lists
    def process_list(data_list, section_name, transaction_key):
        for entry in data_list:
            # Extract common key-value pairs
            common_data = {k: v for k, v in entry.items() if not isinstance(v, list)}
            transactions = entry.get(transaction_key, [])
            for transaction in transactions:
                row = {
                    **common_data,
                    **transaction,
                    "section": section_name,
                    "gstin_of_taxpayer": gstin_of_taxpayer,
                    "rtnprd": rtnprd,
                    "gendt": gendt,  # Add the full date
                }
                # Process items if present
                items = transaction.get("items", [])
                for item in items:
                    item_row = {**row, **item}
                    rows.append(item_row)
                if not items:
                    rows.append(row)

    # Process all possible lists
    possible_lists = ["b2b", "cdnr", "b2ba", "cdnra"]
    transaction_keys = {"b2b": "inv", "cdnr": "nt", "b2ba": "inv", "cdnra": "nt"}

    for list_name in possible_lists:
        data_list = docdata.get(list_name, [])
        if data_list:
            process_list(data_list, list_name, transaction_keys[list_name])

    # Convert rows to DataFrame and return along with gendt
    return pd.DataFrame(rows), gendt


class GSTDataProcessor:
    def __init__(self, dataframe):
        """
        Initialize the processor with the DataFrame to process.
        """
        self.df = dataframe.copy()  # Work with a copy to preserve the original data

    def drop_unnecessary_columns(self, COLUMNS_TO_DROP):
        """
        Drop unnecessary columns if they exist in the DataFrame.
        """
        self.df.drop(
            columns=[col for col in COLUMNS_TO_DROP if col in self.df.columns],
            inplace=True,
        )

    def rename_columns(self, COLUMN_MAPPING):
        """
        Rename columns based on their availability in the DataFrame.
        """
        self.df.rename(
            columns={k: v for k, v in COLUMN_MAPPING.items() if k in self.df.columns},
            inplace=True,
        )

    def combine_columns(self):
        """
        Combine 'Supplier Invoice Number' and 'Note Number' into a single column
        only if both columns are available. If only one column is present, it remains unchanged.
        """
        if {"Supplier Invoice Number", "Note Number"}.issubset(self.df.columns):
            self.df["Supplier Invoice Number/Note Number"] = self.df.apply(
                lambda row: (
                    f"{row['Supplier Invoice Number']} / {row['Note Number']}"
                    if pd.notnull(row["Supplier Invoice Number"])
                    and pd.notnull(row["Note Number"])
                    else (
                        row["Supplier Invoice Number"]
                        if pd.notnull(row["Supplier Invoice Number"])
                        else row["Note Number"]
                    )
                ),
                axis=1,
            )
            self.df.drop(
                columns=["Supplier Invoice Number", "Note Number"], inplace=True
            )
        elif "Supplier Invoice Number" in self.df.columns:
            self.df.rename(
                columns={
                    "Supplier Invoice Number": "Supplier Invoice Number/Note Number"
                },
                inplace=True,
            )
        elif "Note Number" in self.df.columns:
            self.df.rename(
                columns={"Note Number": "Supplier Invoice Number/Note Number"},
                inplace=True,
            )

    def reorder_columns(self, NEW_ORDER, ADDITIONAL_COLUMNS):
        """
        Reorder columns based on the specified order and add additional columns at the end if they exist.
        """
        available_columns = [col for col in NEW_ORDER if col in self.df.columns]
        additional_columns = [
            col for col in ADDITIONAL_COLUMNS if col in self.df.columns
        ]
        self.df = self.df[available_columns + additional_columns]

    def replace_values(self):
        """
        Replace values in specific columns if they exist.
        """
        if "Doc Type" in self.df.columns:
            self.df["Doc Type"] = self.df["Doc Type"].replace(
                {"R": "Regular", "C": "Credit Note", "D": "Debit Note"}
            )
        if "Note Supply Type" in self.df.columns:
            self.df["Note Supply Type"] = self.df["Note Supply Type"].replace(
                {"R": "Regular"}
            )

    def format_tax_rate(self):
        """
        Format the 'Applicable % of Tax Rate' column if it exists.
        """
        if "Applicable % of Tax Rate" in self.df.columns:
            self.df["Applicable % of Tax Rate"] = self.df[
                "Applicable % of Tax Rate"
            ].apply(lambda x: f"{x * 100}%")

    def map_place_of_supply(self, POS):
        """
        Map state names to the 'Place of Supply' column if it exists.
        """
        if "Place of Supply" in self.df.columns:
            self.df["Place of Supply"] = self.df["Place of Supply"].apply(
                lambda x: f"{int(x):02}"
            )
            self.df["Place of Supply"] = self.df["Place of Supply"].apply(
                lambda x: f"{x}-{POS.get(x, 'Unknown')}"
            )

    def combine_invoices_per_rates(self):
        sum_columns = ["Taxable Value", "CGST", "SGST", " Cess"]

        other_columns = [
            col
            for col in self.df.columns
            if col
            not in sum_columns
            + ["GSTIN of Supplier", "Supplier Invoice Number/Note Number"]
        ]

        self.df = self.df.groupby(
            ["GSTIN of Supplier", "Supplier Invoice Number/Note Number"], as_index=False
        ).agg(
            {
                **{col: "sum" for col in sum_columns},
                **{col: "first" for col in other_columns},
            }
        )

    def process(
        self, COLUMNS_TO_DROP, COLUMN_MAPPING, NEW_ORDER, ADDITIONAL_COLUMNS, POS
    ):
        """
        Execute all operations on the DataFrame in sequence.
        """
        self.drop_unnecessary_columns(COLUMNS_TO_DROP)
        self.rename_columns(COLUMN_MAPPING)
        self.combine_columns()
        self.combine_invoices_per_rates()
        # self.handle_ammendments()
        self.reorder_columns(NEW_ORDER, ADDITIONAL_COLUMNS)
        self.replace_values()
        self.format_tax_rate()
        self.map_place_of_supply(POS)

        return self.df


def insert_2BData(df, user_id, gst_info_id):
    df.columns = df.columns.str.strip()

    def get_valid_decimal(value, default=0.00):
        if pd.notna(value) and value not in ["None", None, ""]:
            try:
                return float(value)
            except ValueError:
                return default
        return default

    records = []
    for _, row in df.iterrows():
        try:
            supplier_invoice_date = datetime.strptime(
                row["Supplier Invoice Date/Note Date"], "%d-%m-%Y"
            ).date()
            supplier_filing_date = None
            if row.get("Supplier Filing date"):
                supplier_filing_date = datetime.strptime(
                    row["Supplier Filing date"], "%d-%m-%Y"
                ).date()

            # Check if document type is Credit Note
            is_credit_note = row.get("Doc Type", "").strip().lower() == "credit note"

            # Get the decimal values first
            taxable_value = get_valid_decimal(row.get("Taxable Value"))
            cgst = get_valid_decimal(row.get("CGST"))
            sgst = get_valid_decimal(row.get("SGST"))
            igst = get_valid_decimal(row.get("IGST"))
            invoice_value = get_valid_decimal(row.get("Invoice Value"))
            cess = get_valid_decimal(row.get("Cess"))

            # Make them negative only if they're not zero and it's a credit note
            taxable_value = (
                -abs(taxable_value)
                if is_credit_note and taxable_value != 0
                else taxable_value
            )
            cgst = -abs(cgst) if is_credit_note and cgst != 0 else cgst
            sgst = -abs(sgst) if is_credit_note and sgst != 0 else sgst
            igst = -abs(igst) if is_credit_note and igst != 0 else igst
            invoice_value = (
                -abs(invoice_value)
                if is_credit_note and invoice_value != 0
                else invoice_value
            )
            cess = -abs(cess) if is_credit_note and cess != 0 else cess

            records.append(
                Data2B(
                    supplier_gstin=(
                        row.get("GSTIN of Supplier", "")
                        if pd.notna(row.get("GSTIN of Supplier"))
                        else ""
                    ),
                    document_number=(
                        row.get("Supplier Invoice Number/Note Number", "")
                        if pd.notna(row.get("Supplier Invoice Number/Note Number"))
                        else ""
                    ),
                    section=(
                        row.get("Section", "") if pd.notna(row.get("Section")) else ""
                    ),
                    taxable_value=taxable_value,
                    cgst=cgst,
                    sgst=sgst,
                    igst=igst,
                    user_gstin=(
                        row.get("GSTIN of User", "")
                        if pd.notna(row.get("GSTIN of User"))
                        else ""
                    ),
                    return_period=(
                        row.get("Return Period", "")
                        if pd.notna(row.get("Return Period"))
                        else ""
                    ),
                    supplier_name=(
                        row.get("Trade/Legal name of Supplier", "")
                        if pd.notna(row.get("Trade/Legal name of Supplier"))
                        else ""
                    ),
                    document_type=(
                        row.get("Doc Type", "") if pd.notna(row.get("Doc Type")) else ""
                    ),
                    note_supply_type=(
                        row.get("Note Supply Type", "")
                        if pd.notna(row.get("Note Supply Type"))
                        else ""
                    ),
                    document_date=supplier_invoice_date,
                    invoice_value=invoice_value,
                    place_of_supply=(
                        row.get("Place of Supply", "")
                        if pd.notna(row.get("Place of Supply"))
                        else ""
                    ),
                    supply_attract_reverse_charge=(
                        row.get("Supply attract reverse charge", "")
                        if pd.notna(row.get("Supply attract reverse charge"))
                        else ""
                    ),
                    gst_rate_percent=get_valid_decimal(row.get("Gst Rate %")),
                    cess=cess,
                    supplier_filing_date=supplier_filing_date,
                    supplier_filing_period=(
                        row.get("Supplier filing period", "")
                        if pd.notna(row.get("Supplier filing period"))
                        else ""
                    ),
                    itc_availability=(
                        row.get("ITC Availability", "")
                        if pd.notna(row.get("ITC Availability"))
                        else ""
                    ),
                    itc_unavailability_reason=row.get("Reason", "") if pd.notna(row.get("Reason")) else "",
                    applicable_percent_of_tax_rate=str(
                        get_valid_decimal(row.get("Applicable % of Tax Rate"))
                    ),
                    source=row.get("Source", "") if pd.notna(row.get("Source")) else "",
                    irn=row.get("IRN", "") if pd.notna(row.get("IRN")) else "",
                    irn_generated_date=(
                        row.get("IRN Generated Date", "")
                        if pd.notna(row.get("IRN Generated Date"))
                        else ""
                    ),
                    inter_or_intra=(
                        row.get("Inter/Intra", "")
                        if pd.notna(row.get("Inter/Intra"))
                        else ""
                    ),
                    reconciliation_status=False,
                    reconciliation_category=None,
                    user_id=user_id,
                    user_gst_info_id=gst_info_id,
                )
            )
        except Exception as e:
            # print(f"Error processing row: {row.to_dict()}, Error: {e}")
            pass

    Data2B.objects.bulk_create(records)
    # print("     -> 2B Data Inserted Into DB")
    return True


def fetch_2B_data(user, gst_info, financial_year):
    client = SandboxClient()
    auth_token = gst_info.gst_token

    # gst_info_serializer = UserGstInfoSerializer(gst_info)
    # auth_token = gst_info_serializer.data["gst_token"]

    print(f"Starting GSTR-2B fetch for FY: {financial_year}, GSTIN: {gst_info.gstin}")

    # --- Notification: Task Started ---
    send_websocket_notification_sync(
        user_id=user.id,
        user_gst_info_id=gst_info.id,
        module="data_2b_fetch",
        title="GSTR-2B Fetch Started",
        message=f"GSTR-2B data fetch for FY {financial_year} (GSTIN: {gst_info.gstin}) has begun. Please wait...",
        notification_type="info",
        metadata={"financial_year": financial_year, "status": "started", "gstin": gst_info.gstin},
        
    )

    periods_ls = get_financial_year_available_months(financial_year)
    dfs = []
    failed_months = []
    successful_months = []
    for month, year in periods_ls:
        record_exists = TimeRange.objects.filter(
            Q(
                Month=month,
                Year=year,
                status_2B=2,
                user_id=user.id,
                user_gst_info_id=gst_info,
            )
        ).exists()

        if record_exists:
            # print(f"Skipping {month}-{year} as it's already processed.")
            continue

        url = "https://api.sandbox.co.in/gst/compliance/tax-payer/gstrs/gstr-2b/{}/{}".format(
            year, month
        )

        headers = {
            "accept": "application/json",
            "authorization": auth_token,
            "x-api-key": SANDBOX_API_KEY,
            "x-api-version": "1.0",
        }
        response = requests.get(url, headers=headers)
        text_from_response = response.text
        
        # print(
        #     "Extraction Status: ",
        #     json.loads(text_from_response)["code"] == 200
        #     and json.loads(text_from_response)["data"]["status_cd"] == "1",
        # )
        if (
            json.loads(text_from_response)["code"] == 200
            and json.loads(text_from_response)["data"]["status_cd"] == "1"
        ):
            query = Q(
                Month=month,
                Year=year,
                user_id=user.id,
                user_gst_info_id=gst_info,
            )
            TimeRange.objects.filter(query).update(status_2B=2)

            df, genrated_date = process_json_to_dataframe(text_from_response)
            processor = GSTDataProcessor(df)
            processed_df = processor.process(
                COLUMNS_TO_DROP, COLUMN_MAPPING, NEW_ORDER, ADDITIONAL_COLUMNS, POS
            )
            processed_json = processed_df.to_json()
            dfs.append(processed_df)
            successful_months.append(month)

        elif (
            json.loads(text_from_response)["code"] == 200
            and json.loads(text_from_response)["data"]["status_cd"] == "0"
        ):  
            failed_months.append(month)
            query = Q(
                Month=month,
                Year=year,
                user_id=user.id,
                user_gst_info_id=gst_info,
            )
            TimeRange.objects.filter(query).update(status_2B=3)

            

    if dfs:
        # print("There are dfs containing 2B Data")
        superdf = pd.concat(dfs, ignore_index=True)
        superdf = superdf.where(pd.notnull(superdf), "None")

        def handle_amendments(df):
            df["Section"] = df["Section"].astype(str)

            b2b_data = df[df["Section"].isin(["b2b", "b2ba"])].copy()
            b2b_data["Section_rank"] = (
                b2b_data["Section"].map({"b2ba": 1, "b2b": 2}).fillna(3)
            )
            b2b_filtered = b2b_data.sort_values(by="Section_rank").drop_duplicates(
                subset=["GSTIN of Supplier", "Supplier Invoice Number/Note Number"],
                keep="first",
            )

            # Handle cdnr & cdnra
            cdnr_data = df[df["Section"].isin(["cdnr", "cdnra"])].copy()
            cdnr_data["Section_rank"] = (
                cdnr_data["Section"].map({"cdnra": 1, "cdnr": 2}).fillna(3)
            )
            cdnr_filtered = cdnr_data.sort_values(by="Section_rank").drop_duplicates(
                subset=["GSTIN of Supplier", "Supplier Invoice Number/Note Number"],
                keep="first",
            )

            # Add all other sections that don't require amendment handling
            others = df[~df["Section"].isin(["b2b", "b2ba", "cdnr", "cdnra"])]

            # Combine everything
            final_df = pd.concat(
                [b2b_filtered, cdnr_filtered, others], ignore_index=True
            )
            final_df = final_df.drop(
                columns=["Section_rank"], errors="ignore"
            ).sort_values(by="Return Period")

            return final_df.reset_index(drop=True)

        new_df = handle_amendments(superdf)

        insert_2BData(new_df, user.id, gst_info.id)

    month_names = {
        1: 'January', 2: 'February', 3: 'March', 4: 'April',
        5: 'May', 6: 'June', 7: 'July', 8: 'August',
        9: 'September', 10: 'October', 11: 'November', 12: 'December'
    }
    mapped_successful_months = [month_names.get(month_num, f"Month {month_num}") for month_num in successful_months]
    mapped_failed_months = [month_names.get(month_num, f"Month {month_num}") for month_num in failed_months]

    if len(successful_months) == 12:
        send_websocket_notification_sync(
        user_id=user.id,
        user_gst_info_id=gst_info.id,
        module="data_2b_fetch",
        title="GSTR-2B Data Fetched Successfully",
        message=f"GSTR-2B data for FY {financial_year} (GSTIN: {gst_info.gstin}) has been successfully fetched.",
        notification_type="success",
        metadata={"financial_year": financial_year, "status": "completed", "record_count": "N/A", "gstin": gst_info.gstin}
        )
        
    elif len(failed_months) == 12:
        send_websocket_notification_sync(
            user_id=user.id,
            user_gst_info_id=gst_info.id,
            module="data_2b_fetch",
            title="GSTR-2B Fetch Failed",
            message=f"GSTR-2B data fetch for FY {financial_year} (GSTIN: {gst_info.gstin}) failed for all months. Please check if you filed your GSTR-1 for these months.",
            notification_type="error",
            metadata={"financial_year": financial_year, "status": "failed", "failed_months": failed_months, "gstin": gst_info.gstin}
        )
    elif len(successful_months) == 0 and len(failed_months) == 0:
        print("Data already fetched for this FY")
        send_websocket_notification_sync(
            user_id=user.id,
            user_gst_info_id=gst_info.id,
            module="data_2b_fetch",
            title="GSTR-2B Data Already Fetched",
            message=f"Data for FY {financial_year} (GSTIN: {gst_info.gstin}) has already been fetched. No new data available.",
            notification_type="warning",
            metadata={"financial_year": financial_year, "status": "success", "gstin": gst_info.gstin}
        )
    else:

        if successful_months:
            send_websocket_notification_sync(
                user_id=user.id,
                user_gst_info_id=gst_info.id,
                module="data_2b_fetch",
                title="GSTR-2B Fetch Successful for Few Months",
                message=f"GSTR-2B data fetch for FY {financial_year}  successful for the following months: {', '.join(map(str, mapped_successful_months))}.",
                notification_type="warning",
                metadata={"financial_year": financial_year, "status": "failed", "failed_months": mapped_successful_months, "gstin": gst_info.gstin}
            )
        if failed_months:
            send_websocket_notification_sync(
                user_id=user.id,
                user_gst_info_id=gst_info.id,
                module="data_2b_fetch",
                title="GSTR-2B Fetch Failed for Few Months",
                message=f"GSTR-2B data fetch for FY {financial_year} (GSTIN: {gst_info.gstin}) failed for the following months: {', '.join(map(str, mapped_failed_months))}. Please check if you filed your GSTR-1 for these months.",
                notification_type="warning",
                metadata={"financial_year": financial_year, "status": "failed", "failed_months": failed_months, "gstin": gst_info.gstin}
            )
        

    print(f"GSTR-2B fetch for FY: {financial_year}, GSTIN: {gst_info.gstin} completed successfully.")

    return 200


def trigger_2b_fetch(request_body_year, user, gst_info):
    # Fetch 2B Data for the given FY
    periods_ls = get_financial_year_available_months(request_body_year)
    for month, year in periods_ls:
        record_exists = TimeRange.objects.filter(
            Month=month,
            Year=year,
            status_2B=2,
            user_id=user.id,
            user_gst_info_id=gst_info,
        ).exists()

        if not record_exists:
            TimeRange.objects.filter(
                Month=month,
                Year=year,
                user_id=user.id,
                user_gst_info_id=gst_info,
            ).update(status_2B=1)

    # Schedule a task to fetch the 2B Data
    async_task(
        "apps.gst.utils.fetch_2B_data", user, gst_info, request_body_year
    )
