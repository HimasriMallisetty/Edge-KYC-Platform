import os
import time
import hashlib
import logging
import tempfile
import pandas as pd
from datetime import datetime

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.core.s3 import S3Client
from apps.core.sandbox import is_jwt_expired
from apps.authentication.models import UserGstInfo
from apps.gst.utils import (
    get_start_end_period,
    ImportValidator,
    trigger_2b_fetch,
    save_purchase_register_data,
    get_period_name
)
from apps.gst.constants import (
    ERROR_TOKEN_EXPIRED,
    ERROR_MISSING_GSTIN,
    ERROR_MISSING_USERNAME,
    ERROR_MISSING_FY,
    ERROR_PENDING_AUTHENTICATION,
    EXCEPTION_DATA_FETCH,
    ERROR_MISSING_FILE,
    ERROR_INVALID_FILE_FORMAT,
    MESSAGE_FILE_UPLOAD_FAILED,
    MESSAGE_FILE_UPLOAD_SUCCESS,
    EXCEPTION_VALIDATE_PR,
    ERROR_INVALID_YEAR_FORMAT,
    EXCEL_COLUMNS,
    TARGET_COLUMNS
)
from apps.gst.models import PrDataTransactions, PrData, Data2B, ReconciliationReport, TimeRange, UserModificationHistory
from apps.gst.permissions import IsActiveGSTSubscriber
from apps.gst.serializers import PrDataTransactionsSerializer
from apps.gst.utils import PreprocessPurchaseData, revalidate_and_save, get_return_periods

validation_logger = logging.getLogger('validations.log')

class UploadPR(APIView):
    """
    API endpoint to validate and upload a Purchase Register (PR) Excel file for a given GSTIN and financial year.

    Authentication is required.

    Handles file validations, re-upload logic, S3 upload, and data persistence.

    Request Body:
    - gstin (str): GST Identification Number (required)
    - username (str): GST portal username (required)
    - pr_file (file): Excel file (.xls or .xlsx) of PR data (required)
    - year (str): Financial year in 'YYYY-YYYY' format (required)
    - quarter (str): Optional quarter (e.g. "Q1", "Q2")
    - month (str): Optional month number (e.g. "04" for April)
    - reupload_status (str): Flag to indicate if this is a reupload (optional)

    Validations:
    - Only Excel files are accepted
    - Checks GST authentication and token expiry
    - Runs structural and logical validations on the uploaded data
    - If reuploading, clears previous data and resets reconciliation states

    Returns:
    - 200 OK: If validation passes or fails, with appropriate message
    - 404 NOT FOUND: If required fields or authentication is missing
    - 400 BAD REQUEST: If file is invalid, unreadable, or other errors occur
    """

    permission_classes = [IsAuthenticated, IsActiveGSTSubscriber]

    def post(self, request):
        user = request.user

        request_body_gstin = request.data.get("gstin")
        request_body_username = request.data.get("username")
        request_body_pr_file = request.FILES.get("pr_file")
        request_body_year = request.data.get("year")
        request_body_quarter = request.data.get("quarter")
        request_body_month = request.data.get("month")
        reupload_status = request.data.get("reupload_status")

        upload_type = "File Upload"

        if request_body_pr_file is None:
            return Response(
                {"message": ERROR_MISSING_FILE},
                status=status.HTTP_404_NOT_FOUND,
            )

        if request_body_gstin is None:
            return Response(
                {"message": ERROR_MISSING_GSTIN},
                status=status.HTTP_404_NOT_FOUND,
            )

        if request_body_username is None:
            return Response(
                {"message": ERROR_MISSING_USERNAME},
                status=status.HTTP_404_NOT_FOUND,
            )

        if request_body_year is None:
            return Response(
                {"message": ERROR_MISSING_FY},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        validation_logger.info(f"[GST][File Upload][User Id: {user.id}] Upload File API has been hit, payload is proper.")

        # Check for File Extension (Only Excel Allowed)
        allowed_extensions = ["xls", "xlsx"]
        file_name_uploaded = request_body_pr_file.name
        file_extension = os.path.splitext(file_name_uploaded)[1][1:].lower()

        if file_extension not in allowed_extensions:
            validation_logger.info(
                f"[GST][File Upload][User Id: {user.id}] Invalid file format: '{file_extension}' not in allowed extensions {allowed_extensions}"
            )
            return Response(
                {"message": ERROR_INVALID_FILE_FORMAT},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get User GST Information
        gst_info = (
            UserGstInfo.objects.filter(
                user=request.user,
                gstin=request_body_gstin,
                gst_username=request_body_username,
            )
            .order_by("-refreshed_at")
            .first()
        )
        if gst_info is None:
            return Response(
                {"message": ERROR_PENDING_AUTHENTICATION},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if the user token is expired
        user_token = gst_info.gst_token

        if is_jwt_expired(user_token):
            validation_logger.info(f"[GST][File Upload][User Id: {user.id}] Expired token detected for GSTIN: {gst_info.gstin}")
            return Response(
                {"message": ERROR_TOKEN_EXPIRED}, status=status.HTTP_403_FORBIDDEN
            )

        # Get start date and end date based on user selected year, quarter and month
        start_date, end_date = get_start_end_period(
            request_body_year, request_body_quarter, request_body_month
        )

        # Process the Uploaded File
        try:
            file_path = os.path.join("pr_files", file_name_uploaded)
            saved_file_path = default_storage.save(
                file_path, ContentFile(request_body_pr_file.read())
            )

        except Exception as e:
            return Response(
                {"message": f"Error while saving file: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            full_file_path = os.path.join(settings.MEDIA_ROOT, saved_file_path)
            with default_storage.open(saved_file_path, "rb") as file:
                input_pr_df = pd.read_excel(file, engine="openpyxl")
            validation_logger.info(f"[GST][File Upload][User Id: {user.id}] Successfully read Excel file from path: {saved_file_path}")

        except Exception as e:
            validation_logger.info(f"[GST][File Upload][User Id: {user.id}] Failed to read Excel file at path: {saved_file_path} | Error: {str(e)}")
            return Response(
                {"message": f"Error reading the uploaded Excel file."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Store the file in S3
        try:
            s3 = S3Client()
            original_file_name = request_body_pr_file.name.strip()
            file_base_name, file_extension = os.path.splitext(original_file_name)
            file_base_name = file_base_name.replace(" ", "_")
            unique_id = hashlib.md5(
                f"{original_file_name}{time.time()}".encode()
            ).hexdigest()[:8]
            file_name = f"{file_base_name}_{unique_id}{file_extension}"

            if hasattr(request_body_pr_file, "temporary_file_path"):
                local_file_path = request_body_pr_file.temporary_file_path()
            else:
                temp_file = tempfile.NamedTemporaryFile(delete=False)
                temp_file.write(request_body_pr_file.read())
                temp_file.close()
                local_file_path = temp_file.name

            upload_response = s3.upload_file(
                local_file_path, "edgekycdocs", "gst_pr_uploads", file_name
            )
            s3_link_response = upload_response.get("url")
            if s3_link_response is None:
                s3_link_response = "S3 Upload Failed"
        except Exception as e:
            validation_logger.info(f"[GST][File Upload][User Id: {user.id}] Failed to upload file to S3 | File: {original_file_name} | Error: {str(e)}")
            s3_link_response = "S3 Upload Failed"
            return Response(
                {"message": f"Error uploading file to S3."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Run Validation and define the response.
        try:
            processor = PreprocessPurchaseData(input_pr_df, user)
            processor.normalise_column_names()
            preprocessed_dataframe = processor.map_column_names()

            try:
                validation_logger.info(f"[GST][File Upload][User Id: {user.id}] Running file upload validation from {start_date} to {end_date}")
                file_upload_validator = ImportValidator() #If any error occurs here - it gets logged and re raised. 
                file_upload_result = file_upload_validator.run_validation(preprocessed_dataframe, start_date, end_date)
                validation_logger.info(f"[GST][File Upload][User Id: {user.id}] File upload validation completed with result: {file_upload_result}")
            except:
                validation_logger.info(f"[GST][File Upload][User Id: {user.id}] Error occurred during file upload validation from {start_date} to {end_date} | Error: {e}")
                return Response(
                    {"message": "Error occurred during file upload validation."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Calculate period name for Upload Screen table.
            if request_body_month:
                calculated_upload_period = get_period_name("month", request_body_month)
            elif request_body_quarter:
                calculated_upload_period = get_period_name("quarter", request_body_quarter)
            elif request_body_year:
                calculated_upload_period = "April - March"

            # If File Upload has errprs
            if file_upload_result["upload_error_status"]:
                PrDataTransactions.objects.create(
                    user_gst_info=gst_info,

                    period_start=start_date,
                    period_end=end_date,
                    
                    filename=file_name_uploaded,
                    s3_link=s3_link_response,

                    upload_period=calculated_upload_period,
                    upload_type=upload_type,

                    upload_error_status = file_upload_result["upload_error_status"],
                    upload_errors = file_upload_result["upload_error"]
                    
                )
                validation_logger.info(f"[GST][File Upload][User Id: {user.id}] Upload validation failed — errors logged in PrDataTransactions | Errors: {file_upload_result['upload_error']}")

                return Response(
                    {"message": MESSAGE_FILE_UPLOAD_FAILED}, status=status.HTTP_200_OK
                )
            
            # If file upload does not have errors
            else:
                PrDataTransactions.objects.create(
                    user_gst_info=gst_info,

                    period_start=start_date,
                    period_end=end_date,

                    filename=file_name_uploaded,
                    s3_link=s3_link_response,

                    upload_period=calculated_upload_period,
                    upload_type=upload_type,

                    upload_error_status = file_upload_result["upload_error_status"],
                    upload_errors = file_upload_result["upload_error"]
                    
                )

                validation_logger.info(f"[GST][File Upload][User Id: {user.id}] Upload validation passed — proceeding to save PR data")

                try:
                    if reupload_status:
                        yearly_periods = get_return_periods(request_body_year)

                        # Delete entire FY pr data
                        PrData.objects.filter(
                            return_period__in=yearly_periods,
                            user_id=user.id,
                            user_gst_info_id=gst_info.id,
                        ).delete()

                        # Set 2B data reconciliation_status, reconciliation_category to default
                        Data2B.objects.filter(
                            return_period__in=yearly_periods,
                            user_id=user.id,
                            user_gst_info_id=gst_info.id,
                        ).update(reconciliation_status=0, reconciliation_category=None)

                        # Delete entire FY Reconciliation data
                        ReconciliationReport.objects.filter(
                            Q(user_gstin_id=gst_info.id)
                            & (Q(Period_PR__in=yearly_periods) | Q(Period_2B__in=yearly_periods))
                        ).delete()

                        # Delete the user modification history
                        UserModificationHistory.objects.filter(
                            Q(user_gstin_id=gst_info.id)
                            & (Q(Period_PR__in=yearly_periods) | Q(Period_2B__in=yearly_periods))
                        ).delete()

                        # Reset Time Range fields for the givenn FY
                        TimeRange.objects.filter(
                            FY=request_body_year,
                            user_id=user.id,
                            user_gst_info_id=gst_info.id,
                        ).update(
                            status_PR=0,
                            status_reco=0,
                            no_of_doc_PR=0,
                            no_of_doc_2B=0,
                            tax_difference=0,
                            itc_PR=0,
                            itc_2B=0,
                        )



                    save_status, unique_return_periods = save_purchase_register_data(input_pr_df, user, gst_info, upload_type)

                    queryset_from_db = PrData.objects.filter(
                        return_period__in=unique_return_periods,
                        user_id=user.id,
                        user_gst_info_id=gst_info.id,
                    ).order_by("-id")
                    
                    df_from_db = pd.DataFrame(queryset_from_db.values())

                    revalidate_and_save(user, gst_info, input_pr_df=df_from_db)

                    validation_logger.info(f"[GST][File Upload][User Id: {user.id}] Saved purchase register data to database")
                except Exception as e:
                    validation_logger.info(f"[GST][File Upload][User Id: {user.id}] Error occurred while validating or saving purchase register data | Error: {e}")
                    return Response(
                        {"message": "Error occurred while validating or saving purchase register data."},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )


                try:
                    trigger_2b_fetch(request_body_year, user, gst_info) 
                    validation_logger.info(f"[GST][File Upload][User Id: {user.id}] Triggered GSTR-2B data fetch for financial year: {request_body_year}")
                except Exception as e:
                    validation_logger.info(f"[GST][File Upload][User Id: {user.id}] Error occured while trying to trigger GSTR-2B data fetch for financial year: {request_body_year}. | Error: {e}")
                    return Response(
                        {"message": "Error occured while trying to trigger GSTR-2B data fetch."},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

                return Response(
                    {"message": MESSAGE_FILE_UPLOAD_SUCCESS}, status=status.HTTP_200_OK
                )
                
        except Exception as e:
            validation_logger.info(f"[GST][File Upload][User Id: {user.id}] Exception occurred during Uploading a PR File : {str(e)}")
            return Response(
                {"message": f"{EXCEPTION_VALIDATE_PR}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PrTransactions(APIView):
    """
    API endpoint to fetch PR (Purchase Register) transaction data for a specific GSTIN and financial year.
    Authentication is required.

    Request Body:
    - gstin (str): GST Identification Number (required)
    - username (str): GST portal username (required)
    - year (str): Financial year in 'YYYY-YYYY' format (required)

    Validations:
    - Year format must span exactly one year (e.g., "2022-2023")

    Returns:
    - 200 OK: PR transaction data returned successfully.
    - 404 NOT FOUND: If required fields or GST info are missing.
    - 400 BAD REQUEST: If year format is invalid or an error occurs while processing.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        request_body_gstin = request.data.get("gstin")
        request_body_username = request.data.get("username")
        request_body_year = request.data.get("year")

        if request_body_gstin is None:
            return Response(
                {"message": ERROR_MISSING_GSTIN}, status=status.HTTP_404_NOT_FOUND
            )

        elif request_body_username is None:
            return Response(
                {"message": ERROR_MISSING_USERNAME}, status=status.HTTP_404_NOT_FOUND
            )

        elif request_body_year is None:
            return Response(
                {"message": ERROR_MISSING_FY}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            start_year, end_year = map(int, request_body_year.split("-"))
            if end_year - start_year != 1 or start_year < 2000 or end_year > 2100:
                raise ValueError

            start_date = datetime(start_year, 4, 1).date()
            end_date = datetime(end_year, 3, 31).date()

        except ValueError:
            return Response(
                {"message": ERROR_INVALID_YEAR_FORMAT},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            gst_info = (
                UserGstInfo.objects.filter(
                    user=user,
                    gstin=request_body_gstin,
                    gst_username=request_body_username,
                )
                .order_by("-refreshed_at")
                .first()
            )

            if gst_info is None:
                return Response(
                    {"message": ERROR_PENDING_AUTHENTICATION},
                    status=status.HTTP_404_NOT_FOUND,
                )
            else:
                gst_info_id = gst_info.id

            pr_data_entries = PrDataTransactions.objects.filter(
                user_gst_info_id=gst_info_id,
                period_start__gte=start_date,
                period_end__lte=end_date,
            )

            serializer = PrDataTransactionsSerializer(pr_data_entries, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except:
            return Response(
                {"message": EXCEPTION_DATA_FETCH}, status=status.HTTP_400_BAD_REQUEST
            )


class DeleteDocument(APIView):
    permission_classes = [IsAuthenticated, IsActiveGSTSubscriber]

    def post(self, request):
        user = request.user
        request_body_gstin = request.data.get("gstin")
        document_ids = request.data.get("record_ids")

        if document_ids is None:
            return Response(
                {"message": "Record Ids List has not been sent in payload."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if request_body_gstin is None:
            return Response(
                {"message": ERROR_MISSING_GSTIN},
                status=status.HTTP_404_NOT_FOUND,
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

            if gst_info is None:
                return Response(
                    {"message": ERROR_PENDING_AUTHENTICATION},
                    status=status.HTTP_404_NOT_FOUND,
                )

            records = PrData.objects.filter(
                id__in=document_ids,
                user_id=user.id,
                user_gst_info_id=gst_info.id
            )

            if not records.exists():
                return Response(
                    {"message": "No records found for the provided document IDs."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check for reconciled records
            reconciled_records = records.filter(reconciliation_status=True)
            if reconciled_records.exists():
                non_deletable_info = [
                    {
                        "document_number": rec.document_number,
                        "supplier_gstin": rec.supplier_gstin
                    }
                    for rec in reconciled_records
                ]
                validation_logger.warning(f"[GST][Deleting Documents][User id: {user.id}] These documents are reconciled and cannot be deleted: {non_deletable_info}")
                return Response(
                    {
                        "message": "These documents are reconciled and cannot be deleted.",
                        "non_deletable_records": non_deletable_info
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            

            # Handle duplicate records
            duplicates = records.filter(duplicate_status=True)

            all_error_ids = []
            for rec in duplicates:
                if rec.duplicate_errors:
                    try:
                        error_ids = [int(eid.strip()) for eid in rec.duplicate_errors.split(",") if eid.strip().isdigit()]
                        print("error_ids: ",error_ids)
                        all_error_ids.extend(error_ids)
                    except Exception as dup_ex:
                        validation_logger.error(f"[GST][Deleting Documents][User id: {user.id}] Error identifying paired duplicate records {error_ids}")
                        raise
                    
            print("all_error_ids: ", all_error_ids)
            
            # Delete eligible records
            with transaction.atomic():
                deleted_count, _ = records.delete()

            #Validate its paired documents
            try:
                revalidate_and_save(user, gst_info, document_ids=all_error_ids)
            except Exception as dup_ex:
                validation_logger.error(f"[GST][Deleting Documents][User id: {user.id}] Error re validating paired duplicate records {all_error_ids}")
                raise

            if deleted_count == 0:
                validation_logger.warning(f"[GST][Deleting Documents][User id: {user.id}] No matching records found to delete. Ids Given - {document_ids}")
                return Response(
                    {"message": "No matching records found to delete."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            
            validation_logger.info(f"[GST][Deleting Documents][User id: {user.id}] Successfully deleted {deleted_count} records of ids - {document_ids}")
            return Response(
                {"message": f"{deleted_count} record(s) successfully deleted."},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            validation_logger.error(f"[GST][Deleting Documents][User id: {user.id}] Error while deleting documents: {str(e)}, Ids to delete : {document_ids}")
            return Response(
                {"message": "An error occurred while deleting documents."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AddDocument(APIView):
    permission_classes = [IsAuthenticated, IsActiveGSTSubscriber]

    def post(self, request):
        user = request.user

        request_body_gstin = request.data.get("gstin")
        document = request.data.get("document")

        if document is None:
            return Response(
                {"message": "Document to be added is not sent in payload."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if request_body_gstin is None:
            return Response(
                {"message": ERROR_MISSING_GSTIN},
                status=status.HTTP_404_NOT_FOUND,
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

            if gst_info is None:
                return Response(
                    {"message": ERROR_PENDING_AUTHENTICATION},
                    status=status.HTTP_404_NOT_FOUND,
                )
            input_pr_df = pd.DataFrame([document])
            upload_type = "Added Entry"
            save_status, unique_return_periods = save_purchase_register_data(input_pr_df, user, gst_info, upload_type) 

            queryset_from_db = PrData.objects.filter(
                return_period__in=unique_return_periods,
                user_id=user.id,
                user_gst_info_id=gst_info.id,
            ).order_by("-id")
            
            df_from_db = pd.DataFrame(queryset_from_db.values())

            revalidate_and_save(user, gst_info, input_pr_df=df_from_db)

            validation_logger.info(f"[GST][File Upload][User Id: {user.id}] Saved purchase register data to database")

            return Response(
                {"message": "Successfully added a record."},
                status=status.HTTP_200_OK,
            )
        
        except Exception as e:
            validation_logger.error(f"[GST][Deleting Documents][User id: {user.id}] Error while adding document: {str(e)}")
            return Response(
                {"message": "An error occurred while adding documents."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )