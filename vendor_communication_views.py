import collections

from django.db.models import (
    Q
)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status


from apps.gst.models import (
    ReconciliationReport
)

from apps.gst.serializers import (
    RecoInvoiceViewSerializer
)

from apps.gst.constants import (
    ERROR_MISSING_GSTIN,
    ERROR_MISSING_FY,
    ERROR_PENDING_AUTHENTICATION,
    CONTENT_MISSING_IN_2B,
    CONTENT_MISSING_IN_PR,
    CONTENT_ALL_THREE_CATEGORIES,
    CONTENT_MISSING_2B_AND_MISSING_PR,
    CONTENT_MISSING_2B_AND_VALUE_MISMATCH,
    CONTENT_MISSING_PR_AND_VALUE_MISMATCH,
    CONTENT_VALUE_MISMATCH,
    BASE_EMAIL_TEMPLATE
)

from apps.gst.utils import (
    get_return_periods,
    generate_invoice_tables_html
)
from apps.authentication.models import UserGstInfo
from apps.gst.permissions import IsActiveGSTSubscriber
        
class SelectedDocumentsForMailing(APIView):
    permission_classes = [IsAuthenticated, IsActiveGSTSubscriber] 

    def post(self, request):
        """
        Retrieves and organizes reconciliation documents for mailing based on provided criteria.

        This API endpoint allows users to select specific reconciliation documents
        (invoices, debit/credit notes) for a given GSTIN and financial period.
        It supports two primary selection methods: by a list of supplier GSTINs
        or by a list of specific document IDs.

        For each selected document (or documents associated with selected suppliers),
        it categorizes them into 'selections' (explicitly chosen documents) and
        'suggestions' (other relevant documents from the same supplier that
        fall into reconciliation mismatch categories).

        Permissions:
            - User must be authenticated (`IsAuthenticated`).
            - User must be an active GST subscriber (`IsActiveGSTSubscriber`).

        Request Body:
            - `gstin` (str): The GSTIN of the user for whom documents are being retrieved. (Required)
            - `year` (str): The financial year for the documents (e.g., "2023-24"). (Required)
            - `quarter` (str, optional): The financial quarter (e.g., "Q1").
            - `month` (str, optional): The financial month (e.g., "01" for January).
            - `supplier_gstin` (list of str, optional): A list of supplier GSTINs to retrieve
              all relevant mismatch documents for. If provided, `document_ids` is ignored,
              and 'suggestions' will be an empty list.
            - `document_ids` (list of int, optional): A list of specific reconciliation
              document IDs to retrieve. If provided, documents from the same supplier
              that are also mismatches but not explicitly listed will appear in 'suggestions'.

        Responses:
            - 200 OK:
                A list of dictionaries, where each dictionary represents a supplier
                and contains:
                - `supplier_name` (str): The name of the supplier.
                - `selections` (list of dict): A list of serialized reconciliation
                  documents that were explicitly selected or fall under the chosen
                  supplier(s) and are in a mismatch category ("Value Mismatch",
                  "Missing in 2B", "Missing in PR").
                - `suggestions` (list of dict): A list of serialized reconciliation
                  documents from the same suppliers as the selected documents that
                  are in a mismatch category but were not explicitly selected by `document_ids`.
                  This list will be empty if `supplier_gstin` is provided in the request.

            - 400 Bad Request:
                - If neither `supplier_gstin` nor `document_ids` is provided.
                - If the request body is malformed.

            - 404 Not Found:
                - If `gstin` or `year` is missing from the request.
                - If the user's GST information for the provided `gstin` is not found
                  or pending authentication.
                - If no documents are found matching the given criteria.

            - 500 Internal Server Error:
                - If an unexpected error occurs during processing.
        """
        user = request.user
        request_body_gstin = request.data.get("gstin")
        
        request_body_year = request.data.get("year")
        request_body_quarter = request.data.get("quarter")
        request_body_month = request.data.get("month")

        supplier_gstin_list = request.data.get("supplier_gstin")
        document_ids = request.data.get("document_ids")

        if not request_body_gstin:
            return Response(
                {"message": ERROR_MISSING_GSTIN}, status=status.HTTP_404_NOT_FOUND
            )

        if not request_body_year:
            return Response(
                {"message": ERROR_MISSING_FY}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            gst_info = (
                UserGstInfo.objects.filter(
                    user=user,
                    gstin=request_body_gstin
                )
                .order_by("-refreshed_at")
                .first()
            )

            if not gst_info:
                return Response(
                    {"message": ERROR_PENDING_AUTHENTICATION},
                    status=status.HTTP_404_NOT_FOUND,
                )

            yearly_periods = get_return_periods(
                request_body_year, request_body_quarter, request_body_month
            )

            reconciliation_data_queryset = ReconciliationReport.objects.filter(
                Q(user_gstin_id=gst_info.id)
                & (Q(Period_PR__in=yearly_periods) | Q(Period_2B__in=yearly_periods))
            ).exclude(link_status="delinked")

            final_response = []

            # --- Scenario 1: supplier_gstin_list is provided ---
            if supplier_gstin_list:
                if not isinstance(supplier_gstin_list, list):
                    supplier_gstin_list = [supplier_gstin_list] 

                for s_gstin in supplier_gstin_list:
                    supplier_documents = reconciliation_data_queryset.filter(
                        Q(GSTIN_of_Supplier_PR=s_gstin) | Q(GSTIN_of_Supplier_2B=s_gstin)
                    ).order_by('Name_of_Supplier_PR', 'Supplier_Invoice_Number_PR') 

                    selections = []
                    supplier_name = ""

                    for doc in supplier_documents:
                        if not supplier_name and doc.Name_of_Supplier_PR:
                            supplier_name = doc.Name_of_Supplier_PR
                        elif not supplier_name and doc.Name_of_Supplier_2B: 
                            supplier_name = doc.Name_of_Supplier_2B

                        document_no = doc.Supplier_Invoice_Number_PR
                        if not document_no:  
                            document_no = doc.Supplier_Note_Number_PR

                        document_date = doc.Supplier_Invoice_Date_PR
                        if not document_date:  
                            document_date = doc.Supplier_Note_Date_PR

                        if doc.Category in ["Value Mismatch", "Missing in 2B", "Missing in PR"]:
                            serializer = RecoInvoiceViewSerializer(doc)
                            selections.append(serializer.data)
                    
                    if selections:
                        final_response.append({
                            "supplier_name": supplier_name,
                            "selections": selections,
                            "suggestions": [] # Suggestions list is empty when supplier_gstin is given
                        })

            # --- Scenario 2: document_ids is provided ---
            elif document_ids:
                if not isinstance(document_ids, list):
                    document_ids = [document_ids] 

                # Get unique supplier GSTINs from the provided document_ids
                relevant_documents = reconciliation_data_queryset.filter(id__in=document_ids)
                
                unique_supplier_gstins = set()
                for doc in relevant_documents:
                    if doc.GSTIN_of_Supplier_PR:
                        unique_supplier_gstins.add(doc.GSTIN_of_Supplier_PR)
                    elif doc.GSTIN_of_Supplier_2B:
                        unique_supplier_gstins.add(doc.GSTIN_of_Supplier_2B)

                for s_gstin in unique_supplier_gstins:
                    supplier_documents = reconciliation_data_queryset.filter(
                        Q(GSTIN_of_Supplier_PR=s_gstin) | Q(GSTIN_of_Supplier_2B=s_gstin)
                    ).order_by('Name_of_Supplier_PR', 'Supplier_Invoice_Number_PR')

                    selections = []
                    suggestions = []
                    supplier_name = ""

                    for doc in supplier_documents:
                        # Capture supplier_name from the first document found for this supplier
                        if not supplier_name and doc.Name_of_Supplier_PR:
                            supplier_name = doc.Name_of_Supplier_PR
                        elif not supplier_name and doc.Name_of_Supplier_2B: # Fallback if PR name is missing
                            supplier_name = doc.Name_of_Supplier_2B

                        # Check if the document category is "Value Mismatch" or "Missing in 2B" or "Missing in PR"
                        if doc.Category in ["Value Mismatch", "Missing in 2B", "Missing in PR"]:
                            document_no = doc.Supplier_Invoice_Number_PR
                            if not document_no:  
                                document_no = doc.Supplier_Note_Number_PR

                            document_date = doc.Supplier_Invoice_Date_PR
                            if not document_date:  
                                document_date = doc.Supplier_Note_Date_PR

                            serializer = RecoInvoiceViewSerializer(doc)
                            
                            if doc.id in document_ids:
                                selections.append(serializer.data)
                            else:
                                suggestions.append(serializer.data)
                    
                    # Only add if there are selections or suggestions for this supplier
                    if selections or suggestions:
                        final_response.append({
                            "supplier_name": supplier_name,
                            "selections": selections,
                            "suggestions": suggestions
                        })
            else:
                # If neither supplier_gstin nor document_ids are provided
                return Response(
                    {"message": "Either 'supplier_gstin' or 'document_ids' must be provided."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not final_response:
                return Response(
                    {"message": "No documents found for the given criteria."},
                    status=status.HTTP_404_NOT_FOUND
                )

            return Response(final_response, status=status.HTTP_200_OK)
        
        except:
            return Response(
                {"message": "Error occured while trying to fetch selected documents for mailing."}, status=status.HTTP_404_NOT_FOUND
            )

class DraftMail(APIView):
    permission_classes = [IsAuthenticated, IsActiveGSTSubscriber] 

    def post(self, request):
        """
        Generates draft email content for selected reconciliation documents.

        This endpoint takes a list of reconciliation report IDs and a user's GSTIN
        to generate a draft email. The emails are grouped by supplier, and the
        content of each email dynamically changes based on the types of discrepancies
        found among the selected documents for that supplier. It includes a
        summary table of the selected invoices.

        Permissions:
            - User must be authenticated (`IsAuthenticated`).
            - User must be an active GST subscriber (`IsActiveGSTSubscriber`).

        Request Body:
            - `gstin` (str): The GSTIN of the user initiating the mail draft. (Required)
            - `selected_document_ids` (list of int): A list of integer IDs of the
              `ReconciliationReport` objects for which draft emails need to be generated. (Required)

        Responses:
            - 200 OK:
                A list of dictionaries, where each dictionary represents a draft email
                for a unique supplier and contains:
                - `supplier_name` (str): The name of the supplier.
                - `to` (str): An empty string, to be filled by the client (recipient email).
                - `cc` (str): An empty string, to be filled by the client (CC recipients).
                - `bcc` (str): An empty string, to be filled by the client (BCC recipients).
                - `subject` (str): The subject line of the email, dynamically generated
                  based on discrepancy types.
                - `email_body` (str): The HTML content of the email body, including
                  a category-based introductory message and a tabular summary of invoices.
                - `invoice_summary` (dict): A summary of the selected invoices:
                    - `vendor` (str): The supplier's name.
                    - `gstin` (str): The supplier's GSTIN.
                    - `invoices` (str): A string indicating the count of selected invoices (e.g., "5 selected").

            - 400 Bad Request:
                - If `selected_document_ids` is missing, not a list, or contains no valid integers.
                - If an unexpected error occurs during mail generation.

            - 404 Not Found:
                - If `gstin` is missing from the request.
                - If the user's GST information for the provided `gstin` is not found
                  or pending authentication.
                - If no reconciliation reports are found for the provided `selected_document_ids`
                  under the user's GSTIN.
        """
        user = request.user
        request_body_gstin = request.data.get("gstin")
        selected_document_ids = request.data.get("selected_document_ids")


        if not request_body_gstin:
            return Response(
                {"message": ERROR_MISSING_GSTIN}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            gst_info = (
                UserGstInfo.objects.filter(
                    user=user,
                    gstin=request_body_gstin
                )
                .order_by("-refreshed_at")
                .first()
            )

            if not gst_info:
                return Response(
                    {"message": ERROR_PENDING_AUTHENTICATION},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # 3. Validate selected_document_ids
            if not selected_document_ids or not isinstance(selected_document_ids, list):
                return Response(
                    {"message": "No document IDs provided or format is incorrect."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # 4. Fetch ReconciliationReport objects based on selected_document_ids
            valid_ids = [doc_id for doc_id in selected_document_ids if isinstance(doc_id, int)]
            if not valid_ids:
                return Response(
                    {"message": "No valid integer document IDs provided."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            reconciliation_reports_queryset = ReconciliationReport.objects.filter(Q(user_gstin_id=gst_info.id) & Q(id__in=valid_ids)).exclude(link_status="delinked")

            if not reconciliation_reports_queryset:
                return Response(
                    {"message": "No reconciliation reports found for the selected IDs."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        
            # Step 1: Serialize all relevant ReconciliationReport objects
            serialized_reports_data = RecoInvoiceViewSerializer(reconciliation_reports_queryset, many=True).data

            # 5. Group reports by GSTIN_of_Supplier_PR (using the serialized data)
            grouped_reports = collections.defaultdict(list)
            for report_data in serialized_reports_data:
                # Based on your example, Supplier GSTIN is within 'Supplier_Details'
                gstin_supplier_pr = report_data.get('Supplier_Details', {}).get('GSTIN')
                if gstin_supplier_pr:
                    grouped_reports[gstin_supplier_pr].append(report_data)

            # 6. Prepare the list of draft mail objects
            draft_mails = []
            for gstin_supplier, reports_list_for_supplier in grouped_reports.items():
                supplier_name = reports_list_for_supplier[0].get('Supplier_Details', {}).get('Name', 'Supplier')
                total_invoices = len(reports_list_for_supplier)

                discrepancy_types = set()
                ids_list = []
                for report_data in reports_list_for_supplier:
                    ids_list.append(report_data.get('id'))
                    category = report_data.get('Invoice_Details', {}).get('Category')
                    if category:
                        discrepancy_types.add(category)
                
                category_based_content = ""
                subject = f"Discrepancy in Invoices while performing GSTR-2B Reconciliation." 

                sorted_discrepancy_types = tuple(sorted(list(discrepancy_types)))

                if sorted_discrepancy_types == ("Missing in 2B",):
                    category_based_content = CONTENT_MISSING_IN_2B.format(total_invoices=total_invoices)
                    # subject = f"Discrepancy in Invoices: Missing in GSTR-2B"
                elif sorted_discrepancy_types == ("Missing in PR",):
                    category_based_content = CONTENT_MISSING_IN_PR.format(total_invoices=total_invoices)
                    # subject = f"Discrepancy in Invoices: Missing in Purchase Register"
                elif sorted_discrepancy_types == ("Value Mismatch",):
                    category_based_content = CONTENT_VALUE_MISMATCH.format(total_invoices=total_invoices)
                    # subject = f"Discrepancy in Invoices: Value Mismatch in GSTR-2B"
                elif sorted_discrepancy_types == ("Missing in 2B", "Value Mismatch"):
                    category_based_content = CONTENT_MISSING_2B_AND_VALUE_MISMATCH.format(total_invoices=total_invoices)
                elif sorted_discrepancy_types == ("Missing in PR", "Value Mismatch"):
                    category_based_content = CONTENT_MISSING_PR_AND_VALUE_MISMATCH.format(total_invoices=total_invoices)
                elif sorted_discrepancy_types == ("Missing in 2B", "Missing in PR"):
                    category_based_content = CONTENT_MISSING_2B_AND_MISSING_PR.format(total_invoices=total_invoices)
                elif sorted_discrepancy_types == ("Missing in 2B", "Missing in PR", "Value Mismatch"):
                    category_based_content = CONTENT_ALL_THREE_CATEGORIES.format(total_invoices=total_invoices)
                else: 
                    category_based_content = f"During the reconciliation, we observed discrepancies in {total_invoices} invoices which require your attention."

                
                tabular_data_html = generate_invoice_tables_html(reports_list_for_supplier, discrepancy_types)

                
                email_body = BASE_EMAIL_TEMPLATE.format(
                    supplier_name=supplier_name,
                    request_body_gstin=request_body_gstin,
                    gstin_supplier=gstin_supplier,
                    category_based_content=category_based_content,
                    tabular_data=tabular_data_html
                )

                draft_mail_object = {
                    "ids" : ids_list,
                    "supplier_name": supplier_name,
                    "to": "",  
                    "cc": "",  
                    "bcc": "", 
                    "subject": subject,
                    "email_body": email_body.replace('\n', ''), 
                    "invoice_summary": {
                        "vendor": supplier_name,
                        "gstin": gstin_supplier,
                        "invoices": f"{total_invoices} selected"
                    },
                }
                draft_mails.append(draft_mail_object)

            return Response(draft_mails, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"message": "An error occured while trying to draft mails for selected documents. Please try again."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
