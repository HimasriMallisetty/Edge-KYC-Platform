def get_document_type_display(doc_type):
    """Helper to convert 'Regular' to 'Regular Invoice'."""
    return "Regular Invoice" if doc_type == "Regular" else doc_type

def generate_missing_2b_table_html(reports_list):
    """Generates HTML table for 'Missing in 2B' category."""
    if not reports_list:
        return ""

    table_header = """
        <thead>
            <tr>
                <th style="border: 1px solid black; padding: 8px; text-align: center;">Document Type</th>
                <th style="border: 1px solid black; padding: 8px; text-align: center;">Document Number</th>
                <th style="border: 1px solid black; padding: 8px; text-align: center;">Document Date</th>
                <th style="border: 1px solid black; padding: 8px; text-align: center;">Taxable Value</th>
                <th style="border: 1px solid black; padding: 8px; text-align: center;">Total Tax</th>
                <th style="border: 1px solid black; padding: 8px; text-align: center;">Total Invoice Value</th>
                <th style="border: 1px solid black; padding: 8px; text-align: center;">Return Period</th>
            </tr>
        </thead>
    """
    # <th>IGST</th>
    # <th>CGST</th>
    # <th>SGST</th>
    table_rows = []
    for report in reports_list:
        table_rows.append(f"""
            <tr>
                <td style="border: 1px solid black; padding: 8px;">{get_document_type_display(report.get('Document_Type', 'N/A'))}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Invoice_Details', {}).get('PR', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Invoice_Date', {}).get('PR', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Taxable_Value', {}).get('PR', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Tax_Value', {}).get('PR', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Total_Value', {}).get('PR', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Return_Period', {}).get('PR', 'N/A')}</td>
            </tr>
        """)
        # <td>{report.get('IGST_PR', 'N/A')}</td>
        # <td>{report.get('CGST_PR', 'N/A')}</td>
        # <td>{report.get('SGST_PR', 'N/A')}</td>

    return f"""
        <p class="note">These are the invoice(s) in our Purchase Register for which we couldn't find any respective entry in GSTR-2B:</p>
        <table style="border: 1px solid black; border-collapse: collapse; width: 100%;"> 
            {table_header}
            <tbody>
                {"".join(table_rows)}
            </tbody>
        </table>
    """

def generate_missing_pr_table_html(reports_list):
    """Generates HTML table for 'Missing in PR' category."""
    if not reports_list:
        return ""

    table_header = """
        <thead>
            <tr>
                <th style="border: 1px solid black; padding: 8px; text-align: center;">Document Type</th>
                <th style="border: 1px solid black; padding: 8px; text-align: center;">Document Number</th>
                <th style="border: 1px solid black; padding: 8px; text-align: center;">Document Date</th>
                <th style="border: 1px solid black; padding: 8px; text-align: center;">Taxable Value</th>
                <th style="border: 1px solid black; padding: 8px; text-align: center;">Total Tax</th>
                <th style="border: 1px solid black; padding: 8px; text-align: center;">Total Invoice Value</th>
                <th style="border: 1px solid black; padding: 8px; text-align: center;">Return Period</th>
            </tr>
        </thead>
    """
    # <th>IGST</th>
    # <th>CGST</th>
    # <th>SGST</th>
    table_rows = []
    for report in reports_list:
        table_rows.append(f"""
            <tr>
                <td style="border: 1px solid black; padding: 8px;">{get_document_type_display(report.get('Document_Type', 'N/A'))}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Invoice_Details', {}).get('2B', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Invoice_Date', {}).get('2B', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Taxable_Value', {}).get('2B', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Tax_Value', {}).get('2B', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Total_Value', {}).get('2B', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Return_Period', {}).get('2B', 'N/A')}</td>
            </tr>
        """)
        # <td>{report.get('IGST_2B', 'N/A')}</td>
        # <td>{report.get('CGST_2B', 'N/A')}</td>
        # <td>{report.get('SGST_2B', 'N/A')}</td>
    return f"""
        <p class="note">These are the invoice(s) we found in GSTR-2B for which we couldn't find any respective entry in Purchase Register:</p>
        <table style="border: 1px solid black; border-collapse: collapse; width: 100%;"> 
            {table_header}
            <tbody>
                {"".join(table_rows)}
            </tbody>
        </table>
    """

def generate_value_mismatch_table_html(reports_list):
    """Generates HTML table for 'Value Mismatch' category."""
    if not reports_list:
        return ""

    table_header = """
       <thead style="border: 1px solid black;">
           <tr>
               <th rowspan="2" style="border: 1px solid black; padding: 8px; text-align: center;">Document Type</th>
               <th colspan="3" style="border: 1px solid black; padding: 8px; text-align: center;">Document Details</th>
               <th colspan="2" style="border: 1px solid black; padding: 8px; text-align: center;">Document Date</th>
               <th colspan="2" style="border: 1px solid black; padding: 8px; text-align: center;">Supplier Details</th>
               <th colspan="2" style="border: 1px solid black; padding: 8px; text-align: center;">Taxable Value</th>
               <th colspan="3" style="border: 1px solid black; padding: 8px; text-align: center;">Total Tax</th>
               <th colspan="2" style="border: 1px solid black; padding: 8px; text-align: center;">Total Value</th>
               <th colspan="2" style="border: 1px solid black; padding: 8px; text-align: center;">Return Period</th>
           </tr>
           <tr>
               <th style="border: 1px solid black; padding: 8px; text-align: center;">GSTR 2B</th>
               <th style="border: 1px solid black; padding: 8px; text-align: center;">PR</th>
               <th style="border: 1px solid black; padding: 8px; text-align: center;">Category</th>
               <th style="border: 1px solid black; padding: 8px; text-align: center;">GSTR-2B</th>
               <th style="border: 1px solid black; padding: 8px; text-align: center;">PR</th>
               <th style="border: 1px solid black; padding: 8px; text-align: center;">Name</th>
               <th style="border: 1px solid black; padding: 8px; text-align: center;">GSTIN</th>
               <th style="1px solid black; padding: 8px; text-align: center;">GSTR 2B</th>
               <th style="border: 1px solid black; padding: 8px; text-align: center;">PR</th>
               <th style="border: 1px solid black; padding: 8px; text-align: center;">GSTR-2B</th>
               <th style="border: 1px solid black; padding: 8px; text-align: center;">PR</th>
               <th style="border: 1px solid black; padding: 8px; text-align: center;">Difference</th>
               <th style="border: 1px solid black; padding: 8px; text-align: center;">GSTR-2B</th>
               <th style="border: 1px solid black; padding: 8px; text-align: center;">PR</th>
               <th style="border: 1px solid black; padding: 8px; text-align: center;">GSTR-2B</th>
               <th style="border: 1px solid black; padding: 8px; text-align: center;">PR</th>
           </tr>
       </thead>
    """
   
    table_rows = []
    for report in reports_list:
        table_rows.append(f"""
            <tr>
                <td style="border: 1px solid black; padding: 8px;">{get_document_type_display(report.get('Document_Type', 'N/A'))}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Invoice_Details', {}).get('2B', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Invoice_Details', {}).get('PR', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Invoice_Details', {}).get('Category', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Invoice_Date', {}).get('2B', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Invoice_Date', {}).get('PR', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Supplier_Details', {}).get('Name', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Supplier_Details', {}).get('GSTIN', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Taxable_Value', {}).get('2B', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Taxable_Value', {}).get('PR', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Tax_Value', {}).get('2B', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Tax_Value', {}).get('PR', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Tax_Value', {}).get('Tax_Difference', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Total_Value', {}).get('2B', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Total_Value', {}).get('PR', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Return_Period', {}).get('2B', 'N/A')}</td>
                <td style="border: 1px solid black; padding: 8px;">{report.get('Return_Period', {}).get('PR', 'N/A')}</td>
            </tr>
        """)

    return f"""
        <p>These are the invoice(s) with value mismatches:</p>
        <table style="border: 1px solid black; border-collapse: collapse; width: 100%;"> 
            {table_header}
            <tbody>
                {"".join(table_rows)}
            </tbody>
        </table>
    """

def generate_invoice_tables_html(reports_list, discrepancy_types_set):
    """
    Generates combined HTML tables based on the discrepancy types present.
    Filters reports by category to generate specific tables.
    """
    html_tables = []

    # Separate reports by category
    missing_2b_reports = [r for r in reports_list if r.get('Invoice_Details', {}).get('Category') == 'Missing in 2B']
    missing_pr_reports = [r for r in reports_list if r.get('Invoice_Details', {}).get('Category') == 'Missing in PR']
    value_mismatch_reports = [r for r in reports_list if r.get('Invoice_Details', {}).get('Category') == 'Value Mismatch']

    # Generate tables for each relevant category
    if "Missing in 2B" in discrepancy_types_set:
        html_tables.append(generate_missing_2b_table_html(missing_2b_reports))
    
    if "Missing in PR" in discrepancy_types_set:
        html_tables.append(generate_missing_pr_table_html(missing_pr_reports))

    if "Value Mismatch" in discrepancy_types_set:
        html_tables.append(generate_value_mismatch_table_html(value_mismatch_reports))
    
    return "".join(html_tables)
