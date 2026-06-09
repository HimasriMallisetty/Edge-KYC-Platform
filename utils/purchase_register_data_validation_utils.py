import os
import re
import json
import logging 
import pandas as pd
from datetime import datetime

from apps.core.sandbox import *

from apps.gst.models import *
from apps.gst.constants import *
from apps.gst.utils.date_formatting_utils import convert_to_date

validation_logger = logging.getLogger('validations')

class ImportValidator:
    def __init__(self):
        self.upload_error_status = False
        self.upload_error_messages = []

    def validate_columns(self, df: pd.DataFrame, allowed_columns: list, mandatory_columns: list):
        print("the df sent: ", df.columns)
        normalized_allowed_cols = {col.strip().lower() for col in allowed_columns}
        normalized_mandatory_cols = {col.strip().lower() for col in mandatory_columns}

        # Check for unexpected columns
        unexpected_columns = [col for col in df.columns if col not in normalized_allowed_cols]
        if unexpected_columns:
            self.upload_error_status = True
            self.upload_error_messages.append(
                f"Unexpected columns found in the file: {', '.join(unexpected_columns)}."
            )

        # Check for missing mandatory columns
        missing_mandatory_cols = [col for col in normalized_mandatory_cols if col not in df.columns]
        if missing_mandatory_cols:
            self.upload_error_status = True
            self.upload_error_messages.append(
                f"Missing mandatory columns in the file: {', '.join(missing_mandatory_cols)}."
            )

    def time_period_validator(self, df: pd.DataFrame, start_date: datetime, end_date: datetime):
        parsed_start_date = convert_to_date(start_date)
        parsed_end_date = convert_to_date(end_date)
        
        for index, row in df.iterrows():
            accounting_date = convert_to_date(row.get('accounting_date'))
            document_date = convert_to_date(row.get('document_date'))
           
            record_date = None

            # Try to parse accounting_date first
            if accounting_date:
                record_date = accounting_date

            # If accounting_date is not available or invalid, use document_date
            if pd.isna(record_date) and document_date:
                record_date = document_date
            
            if pd.isna(record_date):
                self.upload_error_status = True
                self.upload_error_messages.append(
                    f"Row {index + 1}: Neither 'accounting date' nor 'document_date' could be parsed or found."
                )
                continue 
            
            if not (parsed_start_date <= record_date <= parsed_end_date):
                self.upload_error_status = True
                self.upload_error_messages.append(
                    f"Row {index + 1}: The record date '{record_date.strftime('%Y-%m-%d')}' "
                    f"falls outside the allowed time period ({parsed_start_date} to {parsed_end_date})."
                )
    

    def run_validation(self, df: pd.DataFrame, start_date: datetime, end_date: datetime):
        """
        Runs all validations and returns the result in JSON.
        """
        # Reset status and messages
        self.upload_error_status = False
        self.upload_error_messages = []
        

        # Run validations
        self.validate_columns(df, ALLOWED_COLUMNS, MANDATORY_COLUMNS)
        self.time_period_validator(df, start_date, end_date)

        return {
            "upload_error_status": self.upload_error_status,
            "upload_error": " ".join(self.upload_error_messages) if self.upload_error_messages else None
        }

class PurchaseRegisterDataValidator:
    """
    Validates Purchase Register data rows. Designed to be called on a DataFrame
    and append validation results to the DataFrame itself.
    """

    def __init__(self):
        self.validation_errors_map = {} # To store row-wise errors
        self.duplicate_info_map = {} # To store row-wise duplicate info

    def _log_row_error(self, index, column_name, error_message):
        """
        Helper to log errors for a specific row, using the normalized column name
        from self.column_mapping.
        """

        if index not in self.validation_errors_map:
            self.validation_errors_map[index] = {}
        
        self.validation_errors_map[index][column_name] = error_message

    def validate_gstin_format(self, df: pd.DataFrame):
        """
        Validates the format of 'supplier_gstin' and 'user_gstin' columns.
        Adds errors directly to the internal error map.
        """
        for col_name in ["supplier_gstin", "user_gstin"]:
            if col_name not in df.columns:
                continue

            gstin_series = df[col_name].astype(str).str.strip()
            invalid_mask = gstin_series.apply(lambda x: bool(x) and not re.fullmatch(GSTIN_REGEX, x))

            if invalid_mask.any():
                for index in df[invalid_mask].index:
                    value = df.loc[index, col_name]
                    self._log_row_error(
                        index,
                        col_name,
                        f"Invalid GSTIN format."
                    )

    def validate_mandatory_missing_values(self, df: pd.DataFrame):
        """
        Validates that mandatory columns have no missing or empty values.
        Adds errors directly to the internal error map.
        """

        for col_orig in MANDATORY_COLUMNS:
            col_norm = col_orig.lower().strip() 

            if col_norm not in df.columns:
                for index in df.index:
                    self._log_row_error(
                        index,
                        col_orig,
                        f"'{col_orig}' column cannot be missing, this field is requird for reconciliation or report generation.",
                        
                    )
                continue 

            # Check for NaN and empty strings (after stripping whitespace)
            missing_mask = df[col_norm].isna() | (df[col_norm].astype(str).str.strip() == '')

            if missing_mask.any():
                for index in df[missing_mask].index:
                    self._log_row_error(
                        index,
                        col_orig,
                        f"This column cannot be empty, this field is requird for reconciliation or report generation."
                    )

    def validate_document_type(self, df: pd.DataFrame):
        """
        Validates that 'document_type' column contains only allowed values.
        Adds errors directly to the internal error map.
        """
        col_name = "document_type"
        if col_name not in df.columns:
            return 

        # Normalize and strip document type values for comparison
        doc_type_series = df[col_name].astype(str).str.strip().str.lower()
        allowed_types_lower = [dt.lower() for dt in DOCUMENT_TYPES_ALLOWED]

        invalid_mask = ~doc_type_series.isin(allowed_types_lower)
        invalid_mask = invalid_mask & (doc_type_series != "")

        if invalid_mask.any():
            for index in df[invalid_mask].index:
                value = df.loc[index, col_name]
                self._log_row_error(
                    index,
                    col_name,
                    f"Invalid document type '{value}'. Allowed values are: {', '.join(DOCUMENT_TYPES_ALLOWED)}. Please follow this terminology."
                )

    def validate_invoice_number_length(self, df: pd.DataFrame):
        """
        Validates that 'document_number' does not exceed max length.
        Adds errors directly to the internal error map.
        """
        col_name = "document_number"
        if col_name not in df.columns:
            return # Handled by mandatory column check if applicable

        invoice_num_series = df[col_name].astype(str).str.strip()
        length_mask = invoice_num_series.apply(lambda x: len(x) > MAX_INVOICE_NUMBER_LENGTH if pd.notna(x) and x != '' else False)

        if length_mask.any():
            for index in df[length_mask].index:
                value = df.loc[index, col_name]
                self._log_row_error(
                    index,
                    col_name,
                    f"Invoice number '{value}' exceeds maximum length of {MAX_INVOICE_NUMBER_LENGTH} characters."
                )

    def validate_numerical_values(self, df: pd.DataFrame):
        """
        Validates that specified columns contain only numerical values.
        Converts them to numeric where possible, logs errors for non-convertible.
        """
        numerical_columns = [
            "invoice_value", "taxable_value", "igst", "cgst", "sgst", "cess"
        ]

        for col_name in numerical_columns:
            if col_name not in df.columns:
                continue

            # Attempt to convert to numeric, coercing errors to NaN
            # Store original values to report in error message
            original_values = df[col_name].copy()
            df[col_name] = pd.to_numeric(df[col_name], errors='coerce')

            # Identify rows where conversion failed (now NaN) but original was not NaN or empty
            # This distinguishes actual non-numeric entries from truly missing ones
            non_numeric_mask = df[col_name].isna() & original_values.notna() & (original_values.astype(str).str.strip() != '')

            if non_numeric_mask.any():
                for index in df[non_numeric_mask].index:
                    original_value = original_values.loc[index]
                    self._log_row_error(
                        index,
                        col_name,
                        f"Non-numerical value '{original_value}' found in '{col_name}' column. Expected a number."
                    )

    def validate_dates(self, df: pd.DataFrame):
        """
        Validates date columns ('Accounting Date', 'document_date').
        Attempts to convert to datetime objects, logs errors for invalid formats.
        """
        date_columns = ["accounting_date", "document_date"]

        for col_name in date_columns:
            if col_name not in df.columns:
                continue

            # Create a new series for date conversion to avoid modifying original df during check
            # but allow original df to be updated if conversion is successful
            original_date_series = df[col_name].copy()

            # Attempt to convert to datetime, coercing errors to NaT (Not a Time)
            # Use errors='coerce' to turn invalid parses into NaT without raising an error
            converted_dates = pd.to_datetime(original_date_series, errors='coerce', dayfirst=True) # Assuming dayfirst format for robustness

            # Identify rows where conversion failed but original was not empty/NaT
            invalid_date_mask = converted_dates.isna() & original_date_series.notna() & (original_date_series.astype(str).str.strip() != '')

            if invalid_date_mask.any():
                for index in df[invalid_date_mask].index:
                    original_value = original_date_series.loc[index]
                    self._log_row_error(
                        index,
                        col_name,
                        f"Invalid date format '{original_value}' in '{col_name}' column. Expected a valid date format (e.g., DD-MM-YYYY, YYYY-MM-DD).",
                        "date_format_error"
                    )
            # Update the DataFrame with the cleaned (or NaT) date values for consistency
            df[col_name] = converted_dates

    
    def run_validations(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Orchestrates all validations and adds validation status/details columns to the DataFrame.
        Modifies the DataFrame in-place and returns it.
        """
        print("Dataframe sent for validations columns: ", df.columns)
        
        self.validation_errors_map = {}
        self.duplicate_info_map = {}
        

        df.columns = df.columns.str.lower().str.strip()

        # Run individual validations
        self.validate_mandatory_missing_values(df)
        print("validate_mandatory_missing_values")
        self.validate_gstin_format(df)
        print("validate_gstin_format")
        self.validate_document_type(df)
        print("validate_document_type")
        self.validate_invoice_number_length(df)
        print("validate_invoice_number_length")
        self.validate_numerical_values(df) # This also attempts conversion
        print("validate_numerical_values")
        self.validate_dates(df) # This also attempts conversion
        print("validate_dates")

        # Add validation columns to the DataFrame
        df['validation_error_status'] = False
        df['validation_errors'] = None


        for index in df.index:
            row_errors = self.validation_errors_map.get(index)
            row_duplicates = self.duplicate_info_map.get(index)

            if row_errors:
                df.loc[index, 'validation_error_status'] = True
                df.loc[index, 'validation_errors'] = json.dumps(row_errors)
        
        
        print("\nFinal DataFrame Columnas after validations and column renaming:", df.columns)

        return df


def validate_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Identifies duplicate rows based on DUPLICATE_CHECK_COLUMNS.
    Adds 'duplicate_status' and 'duplicate_errors' columns.
    Logs steps using validation_logger.
    Returns the updated DataFrame.
    """

    validation_logger.info("Starting duplicate validation process.")
    print()
    print(df.columns)
    print()
    print(df['id'].tolist())


    # Normalize column names
    df.columns = [col.lower().strip() for col in df.columns]

    # Check for missing columns
    missing_cols = [col for col in DUPLICATE_CHECK_COLUMNS if col not in df.columns]
    if missing_cols:
        msg = f"Missing required columns for duplicate check: {', '.join(missing_cols)}"
        validation_logger.error(msg)
        df['duplicate_status'] = False
        df['duplicate_errors'] = ''
        return df

    # Prepare DataFrame for duplicate check
    df_for_dup_check = df[DUPLICATE_CHECK_COLUMNS].copy()
    for col in DUPLICATE_CHECK_COLUMNS:
        if df_for_dup_check[col].apply(lambda x: isinstance(x, (dict, list, set))).any():
            df_for_dup_check[col] = df_for_dup_check[col].apply(
                lambda x: json.dumps(x, sort_keys=False) if isinstance(x, dict)
                else str(x) if isinstance(x, (list, set))
                else x
            ).astype(str)
        else:
            df_for_dup_check[col] = df_for_dup_check[col].astype(str)

    # Identify duplicates
    duplicates_mask = df_for_dup_check.duplicated(subset=DUPLICATE_CHECK_COLUMNS, keep=False)
    df['duplicate_status'] = False
    df['duplicate_errors'] = ''

    if duplicates_mask.any():
        validation_logger.info("Duplicates found. Populating error flags and details.")
        grouped = df_for_dup_check[duplicates_mask].groupby(DUPLICATE_CHECK_COLUMNS)

        for _, group in grouped:
            group_indices = group.index.tolist()
            group_ids = [df.loc[i, 'id'] for i in group_indices]

            if len(group_indices) > 1:
                for idx in group_indices:
                    current_id = df.loc[idx, 'id']
                    # Exclude the current ID
                    other_ids = [str(id_) for id_ in group_ids if id_ != current_id]
                    df.at[idx, 'duplicate_status'] = True
                    df.at[idx, 'duplicate_errors'] = ",".join(other_ids)
                    validation_logger.info(
                        f"Row with ID {current_id} marked as duplicate with IDs: {','.join(other_ids)}"
                    )

    else:
        validation_logger.info("No duplicates found.")

    validation_logger.info("Duplicate validation process completed.")
    return df

