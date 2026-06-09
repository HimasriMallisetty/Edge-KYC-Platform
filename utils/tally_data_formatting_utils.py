import pandas as pd
from datetime import datetime 

def process_tally_json(json_data):
    """
    Processes a Tally JSON file content (as a Python dictionary) and returns a pandas DataFrame
    with specific invoice details, including new and updated fields based on Tally data structure.

    Args:
        file_content_json (dict): The parsed JSON content of the Tally export,
                                  typically obtained from a Tally XML export converted to JSON.

    Returns:
        pandas.DataFrame: A DataFrame containing detailed invoice/voucher information.
    """
    # Navigate to the list of Tally messages (vouchers)
    tally_messages = json_data.get('BODY', {}).get('IMPORTDATA', {}).get('REQUESTDATA', {}).get('TALLYMESSAGE', [])

    # Initialize a list to store dictionaries of extracted data for each voucher
    extracted_data = []

    # Ensure tally_messages is always treated as a list, even if it's a single dictionary
    if isinstance(tally_messages, dict):
        tally_messages = [tally_messages]


    # Iterate through each voucher message
    for message in tally_messages:
        if 'VOUCHER' not in message:
            continue 
        
        voucher = message.get('VOUCHER', {}) 

        all_ledger_entries = voucher.get("LEDGERENTRIES.LIST")
        if all_ledger_entries is None:
            all_ledger_entries = voucher.get("ALLLEDGERENTRIES.LIST")

        skip_condition = True
        if all_ledger_entries and isinstance(all_ledger_entries, list) and len(all_ledger_entries) > 0:
            # print(len(all_ledger_entries), "ledger entries found")
            for ledger_entry in all_ledger_entries:
                ledger_name = ledger_entry.get('LEDGERNAME', '')
                ledger_name = ledger_name.lower()
                # print("ledger_name:", ledger_name)
                if ('igst' in ledger_name or 'sgst' in ledger_name or 'cgst' in ledger_name):
                    is_deemed_positive = ledger_entry.get('ISDEEMEDPOSITIVE', '')
                    # print("is_deemed_positive:", is_deemed_positive)
                    if is_deemed_positive == 'Yes':
                        skip_condition = False
                        break
            
        if skip_condition:
            continue 
        
        # --- Extracting Direct Fields and Mapping to Desired Column Names ---
        # GST details 
        user_gstin = voucher.get('CMPGSTIN', '')
        supplier_name = voucher.get('PARTYLEDGERNAME', '')
        supplier_gstin = voucher.get('PARTYGSTIN', '')
        voucher_type = voucher.get('VOUCHERTYPENAME', '')          

        # Date extraction and formatting
        raw_accounting_date = voucher.get('DATE', '')
        # Use REFERENCEDATE for Invoice Date if available, fallback to DATE
        raw_invoice_date = voucher.get('REFERENCEDATE', raw_accounting_date)
        # Convert dates to YYYY-MM-DD format
        accounting_date_formatted = ''
        if raw_accounting_date and isinstance(raw_accounting_date, str) and len(raw_accounting_date) == 8:
            try:
                accounting_date_formatted = datetime.strptime(raw_accounting_date, '%Y%m%d').strftime('%Y-%m-%d')
            except ValueError:
                pass 
        
        invoice_date_formatted = ''
        if raw_invoice_date and isinstance(raw_invoice_date, str) and len(raw_invoice_date) == 8:
            try:
                invoice_date_formatted = datetime.strptime(raw_invoice_date, '%Y%m%d').strftime('%Y-%m-%d')
            except ValueError:
                pass 

        # Tally-specific identifiers
        tally_guid = voucher.get('GUID', '')
        voucher_number = voucher.get('VOUCHERNUMBER', '')
        
        # Location details
        place_of_supply = voucher.get('PLACEOFSUPPLY', '')
        
        # Invoice number - specifically from REFERENCE key
        invoice_number = voucher.get('REFERENCE', '')

        voucher_type_lower = voucher_type.lower()

        # Document Type based on VOUCHERTYPENAME (already extracted above for condition)
        document_type = 'Regular' 
        if 'purchase' in voucher_type_lower or 'sales' in voucher_type_lower:
            document_type = 'Regular'
        elif 'credit note' in voucher_type_lower:
            document_type = 'Credit Note'
        elif 'debit note' in voucher_type_lower:
            document_type = 'Debit Note'

        # --- Initialize Calculated Values ---
        invoice_value = 0.0
        taxable_value = 0.0
        igst_amount = 0.0
        cgst_amount = 0.0
        sgst_amount = 0.0
        cess_amount = 0.0 

        # --- Calculate Invoice Value and GST Amounts from ALLLEDGERENTRIES.LIST ---
        

        if all_ledger_entries:
            # Ensure all_ledger_entries is always a list for uniform processing
            if isinstance(all_ledger_entries, dict):
                all_ledger_entries = [all_ledger_entries]

            # Set invoice_value from the first ledger entry's amount
            if all_ledger_entries:
                try:
                    invoice_value = abs(float(all_ledger_entries[0].get("AMOUNT", 0.0)))
                except (ValueError, TypeError):
                    invoice_value = 0.0
                
            # Iterate through all ledger entries to sum up GST amounts
            for ledger_entry in all_ledger_entries:
                ledger_name = str(ledger_entry.get("LEDGERNAME", "")).lower() # Ensure it's a string before .lower()
                
                try:
                    amount = abs(float(ledger_entry.get("AMOUNT", 0.0)))
                except (ValueError, TypeError):
                    amount = 0.0

                if 'igst' in ledger_name:
                    igst_amount += abs(amount)
                elif 'cgst' in ledger_name:
                    cgst_amount += abs(amount)
                elif 'sgst' in ledger_name:
                    sgst_amount += abs(amount)
                elif 'cess' in ledger_name:
                    cess_amount += abs(amount)
            
            # Calculate taxable_value as invoice_value minus the sum of all tax components.
            # Assuming invoice_value includes taxes for now.
            taxable_value = invoice_value - (igst_amount + cgst_amount + sgst_amount + cess_amount)
            # Ensure taxable_value doesn't go below zero due to floating point inaccuracies or data anomalies
            taxable_value = max(0.0, taxable_value)

        def clean_field(value):
            return "" if value == {} else value
        
        # --- Append extracted and calculated data for the current voucher ---
        extracted_data.append({
            'accounting_date': accounting_date_formatted,
            'document_date': invoice_date_formatted,

            'tally_guid': tally_guid,
            'voucher_number': voucher_number,

            'place_of_supply': place_of_supply,
            
            'supplier_name': clean_field(supplier_name),
            'supplier_gstin': clean_field(supplier_gstin),
            'user_gstin': user_gstin,
            
            'document_number': clean_field(invoice_number),
            
            'document_type': document_type,
            
            'invoice_value': invoice_value,
            'taxable_value': taxable_value,
            'igst': igst_amount,
            'cgst': cgst_amount,
            'sgst': sgst_amount,
            'cess': cess_amount,
            'voucher_type': voucher_type,  # Added voucher type for reference
            
        })
        # print(extracted_data)

    # Create a Pandas DataFrame from the list of extracted data
    df = pd.DataFrame(extracted_data)

    # # --- Remove rows with empty values in specified columns ---
    # columns_to_check = [
    #     'accounting_date',
    #     'document_date',
    #     'supplier_name',
    #     'supplier_gstin',
    #     'user_gstin',
    #     'document_number',
    #     'document_type',
    #     'invoice_value',
    #     'taxable_value'
    # ]

    # # Drop rows where any of the specified columns have an empty string or 0.0 for numeric values
    # # For numeric columns, 0.0 is considered "empty" in this context as per the original logic
    # for col in columns_to_check:
    #     if col in ['invoice value', 'taxable value']:
    #         df = df[df[col] != 0.0]
    #     else:
    #         df = df[(df[col].astype(str).str.strip() != '') & (df[col].astype(str).str.strip() != '{}')]


    # Delete Transactions with no accounting_date and document_date or voucher_type as journal
    df['accounting_date'] = df['accounting_date'].astype(str).str.strip()
    df['document_date'] = df['document_date'].astype(str).str.strip()
    df['voucher_type'] = df['voucher_type'].astype(str).str.strip().str.lower()

    # Define condition: both dates empty OR voucher_type is 'journal'
    condition = (
        ((df['accounting_date'] == '') & (df['document_date'] == '')) |
        (df['voucher_type'] == 'journal')
    )

    print("Voucher numbers of records to be deleted:")
    print(df.loc[condition, 'voucher_number'])
    
    # Drop rows that match the condition
    df = df[~condition].reset_index(drop=True)


    return df
