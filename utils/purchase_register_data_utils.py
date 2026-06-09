import uuid
import json
import math
import logging
import pandas as pd
from django.db.models import Q
from django.db import transaction

from apps.gst.models import (
    PrData,
    TimeRange,
    PrDataTransactions
)

from apps.gst.utils.date_formatting_utils import (
    get_period_name,
    convert_to_date
)
from apps.gst.utils.purchase_register_data_validation_utils import PurchaseRegisterDataValidator

validation_logger = logging.getLogger("validations.log")

def save_purchase_register_data(input_pr_df, user, gst_info, upload_type):
    
    # try:
    #     validation_logger.info(f"[GST][User id : {user.id}] Running PR data validations")
    #     pr_validator = PurchaseRegisterDataValidator()
    #     input_pr_df = pr_validator.run_validations(input_pr_df.copy()) 
    # except:
    #     validation_logger.info(f"[GST][User id : {user.id}] Error occurred during PR data validation | Error: {e}")
    #     raise

    try:
        list_of_return_periods = []
        pr_data_objects_to_create = []

        validation_logger.info(f"[GST][User id : {user.id}] Validated PR DataFrame info:\n{input_pr_df.dtypes}\n\nMissing values per column:\n{input_pr_df.isnull().sum()}")

        
        for _, row in input_pr_df.iterrows():
            document_type = row.get("document_type", None)
            if pd.isna(document_type):
                document_type = ""
            is_credit_note = document_type.strip().lower() == "credit note"
            
            invoice_value = -abs(row["invoice_value"]) if is_credit_note and pd.notna(row["invoice_value"]) else (row["invoice_value"] if pd.notna(row["invoice_value"]) else 0.00)
            taxable_value = -abs(row["taxable_value"]) if is_credit_note and pd.notna(row["taxable_value"]) else (row["taxable_value"] if pd.notna(row["taxable_value"]) else 0.00)
            igst = -abs(row["igst"]) if is_credit_note and pd.notna(row["igst"]) else (row["igst"] if pd.notna(row["igst"]) else 0.00)
            cgst = -abs(row["cgst"]) if is_credit_note and pd.notna(row["cgst"]) else (row["cgst"] if pd.notna(row["cgst"]) else 0.00)
            sgst = -abs(row["sgst"]) if is_credit_note and pd.notna(row["sgst"]) else (row["sgst"] if pd.notna(row["sgst"]) else 0.00)
            cess = -abs(row.get("cess", None)) if is_credit_note and pd.notna(row.get("cess", None)) else (row.get("cess", None) if pd.notna(row.get("cess", None)) else 0.00)


            return_period = row.get("return_period", None)

            if not return_period or pd.isna(return_period):
                accounting_date = convert_to_date(row.get("accounting_date", None))
                if pd.isna(accounting_date): # or accounting_date is None:
                    invoice_date = convert_to_date(row.get("document_date", None))
                    accounting_date = invoice_date
                if not pd.isna(accounting_date):
                    return_period = accounting_date.strftime("%m%Y")
                    list_of_return_periods.append(return_period)
                else:
                    raise ValueError("Accounting date or Document date is required to calculate return period.")

            def clean_value(val):
                if isinstance(val, float) and (str(val).lower() == 'nan' or str(val).lower() == 'none'):
                    return None
                if isinstance(val, str) and val.strip().lower() in ['nan', 'na', 'none', 'null', '']:
                    return None
                return val

            supplier_gstin = clean_value(row.get("supplier_gstin", None))
            document_number = clean_value(row.get("document_number", None))

            current_row_data = {
                "supplier_gstin": clean_value(supplier_gstin),
                "supplier_name": clean_value(row.get("supplier_name", None)),
                "document_type": document_type,
                "user_gstin": clean_value(row.get("user_gstin", None)),
                "inter_intra": None,
                "return_period": return_period,
                "document_number": document_number,
                "document_date": convert_to_date(row.get("document_date", None)),
                "place_of_supply": clean_value(row.get("place_of_supply", None)),
                "invoice_value": invoice_value,
                "taxable_value": taxable_value,
                "igst": igst,
                "cgst": cgst,
                "sgst": sgst,
                "cess": cess,
                "accounting_date": convert_to_date(row.get("accounting_date", None)),
                "internal_reference_document_number": clean_value(row.get("internal_reference_document_number", None)),
                "internal_counter_party_code": clean_value(row.get("internal_counter_party_code", None)),
                "plant_code": clean_value(row.get("plant_code", None)),
                "internal_field_1": clean_value(row.get("internal_field_1", None)),
                "internal_field_2": clean_value(row.get("internal_field_2", None)),
                "internal_field_3": clean_value(row.get("internal_field_3", None)),
                "internal_field_4": clean_value(row.get("internal_field_4", None)),
                "internal_field_5": clean_value(row.get("internal_field_5", None)),
                "reconciliation_status": False,
                "reconciliation_category": None,
                "upload_type": upload_type,
                "guid": clean_value(row.get("guid", None)),
                "voucher_number": clean_value(row.get("voucher_number", None)),
                "voucher_type": clean_value(row.get("voucher_type", None)),
                "user_id": user.id,
                "user_gst_info_id": gst_info.id
            }
            pr_data_objects_to_create.append(PrData(**current_row_data))

        PrData.objects.bulk_create(pr_data_objects_to_create)
        print("saved data")
        validation_logger.info(f"[GST][User Id: {user.id}] Data Successfully Inserted into the database.")

        # Turn status_PR true for the available months.
        unique_return_periods = sorted(list(set(list_of_return_periods)))
        print("unique_return_periods", unique_return_periods)
       

        unique_return_periods_parsed = []
        for mmyyyy in unique_return_periods:
            print("mmyyyy", mmyyyy)
            if len(mmyyyy) == 6 and mmyyyy.isdigit(): # Basic validation
                month = int(mmyyyy[:2])
                year = int(mmyyyy[2:])
                unique_return_periods_parsed.append([month, year])
            else:
                
                print(f"Warning: Invalid 'return period' format found: {mmyyyy}. Skipping.")
                raise ValueError(
                    f"Invalid 'return period' format found: {mmyyyy}. Expected format is MMYYYY."
                )
            
        print("unique_return_periods_parsed : ", unique_return_periods_parsed)
        
        if unique_return_periods_parsed:
            query = Q()
            for month, year in unique_return_periods_parsed:
                query |= Q(
                    Month=month,
                    Year=year,
                    user_id=user.id,
                    user_gst_info_id=gst_info.id,
                )     

            if query.children:
                TimeRange.objects.filter(query).update(status_PR=True)

        return True, unique_return_periods
    
    except Exception as e:
        print(e)
        raise
 