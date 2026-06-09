import os
from datetime import datetime
import pandas as pd
from django.db.models import Q
import logging

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.authentication.models import UserGstInfo
from apps.gst.models import PrDataTransactions
from apps.gst.utils import (
    process_tally_json,
    send_websocket_notification_sync,
    PurchaseRegisterDataValidator,
    get_month_quarter_year_from_date,
    save_purchase_register_data,
    trigger_2b_fetch,
    get_return_periods,
    revalidate_and_save,
    get_period_name
)
from apps.gst.constants import (
    ERROR_MISSING_GSTIN,
    ERROR_MISSING_USERNAME,
    ERROR_MISSING_FY,
    ERROR_PENDING_AUTHENTICATION,
    EXCEPTION_DATA_FETCH,
    ERROR_TOKEN_EXPIRED
)
from apps.gst.permissions import IsActiveGSTSubscriber
from apps.core.sandbox import is_jwt_expired

from apps.gst.models import PrData, ReconciliationReport, Data2B, UserModificationHistory, TimeRange

validation_logger = logging.getLogger('validations')

class ProcessDataFromTally(APIView):
    permission_classes = [IsAuthenticated, IsActiveGSTSubscriber]

    def post(self, request):
        user = request.user
        payload_gstin = request.data.get("gstin")
        payload_json = request.data.get("json_data")
        start_date = request.data.get("from_date")
        end_date = request.data.get("to_date")
        reupload_status = request.data.get("reuplaod_status")
        upload_type = "Tally"
        
        validation_logger.info(f"[GST][Tally][User Id: {user.id}] Received Tally data POST request for user {user.id}, GSTIN {payload_gstin}, from {start_date} to {end_date}")
        try:
            gst_info = (
                UserGstInfo.objects.filter(
                    user=request.user,
                    gstin=payload_gstin
                )
                .order_by("-refreshed_at")
                .first()
            )
            if gst_info is None:
                validation_logger.error(f"[GST][Tally][User Id: {user.id}] GST info not found for user {user.id}, GSTIN {payload_gstin}")
                return Response(
                    {"message": ERROR_PENDING_AUTHENTICATION},
                    status=status.HTTP_404_NOT_FOUND,
                )

            user_token = gst_info.gst_token
            if is_jwt_expired(user_token):
                validation_logger.error(f"[GST][Tally][User Id: {user.id}] Token expired for user {user.id}, GSTIN {payload_gstin}")
                return Response(
                    {"message": ERROR_TOKEN_EXPIRED}, status=status.HTTP_403_FORBIDDEN
                )
            
            validation_logger.info("Processing Tally JSON to dataframe")
            input_pr_df = process_tally_json(payload_json)

            if input_pr_df.empty:
                validation_logger.info(f"[GST][Tally][User Id: {user.id}] No valid PR data found in Tally JSON for user {user.id}, GSTIN {payload_gstin}")
                send_websocket_notification_sync(
                    user_id=user.id,
                    user_gst_info_id=gst_info.id,
                    module="tally_fetch",
                    title="Tally Data Fetch Completed (No Data)",
                    message=f"No valid Purchase Register data found in the Tally upload for {payload_gstin} in the period {start_date} to {end_date}.",
                    notification_type="warning",
                    metadata={"gstin": payload_gstin, "period_start": str(start_date), "period_end": str(end_date), "status": "completed_no_data"}
                )
                return Response(
                    {"message": "No Purchase Register data found in the provided Tally data."},
                    status=status.HTTP_200_OK
                )

            validation_logger.info("Saving raw Tally dataframe to Excel for debugging")
            output_dir="tally_reports"
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tally_processed_{timestamp}.xlsx"
            filepath = os.path.join(output_dir, filename)
            input_pr_df.to_excel(filepath, index=False)

            validation_logger.info("Extracting month, quarter, year from date range")
            month, quarter, year = get_month_quarter_year_from_date(start_date, end_date)
            
            if reupload_status:
                validation_logger.info(f"Reupload flag is True. Deleting previous FY data for user {user.id}, GSTIN {payload_gstin}")
                yearly_periods = get_return_periods(year)

                PrData.objects.filter(
                    return_period__in=yearly_periods,
                    user_id=user.id,
                    user_gst_info_id=gst_info.id,
                ).delete()

                Data2B.objects.filter(
                    return_period__in=yearly_periods,
                    user_id=user.id,
                    user_gst_info_id=gst_info.id,
                ).update(reconciliation_status=0, reconciliation_category=None)

                ReconciliationReport.objects.filter(
                    Q(user_gstin_id=gst_info.id)
                    & (Q(Period_PR__in=yearly_periods) | Q(Period_2B__in=yearly_periods))
                ).delete()

                UserModificationHistory.objects.filter(
                    Q(user_gstin_id=gst_info.id)
                    & (Q(Period_PR__in=yearly_periods) | Q(Period_2B__in=yearly_periods))
                ).delete()

                TimeRange.objects.filter(
                    FY=year,
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
                validation_logger.info("Previous FY data reset complete")

            if month:
                calculated_upload_period = get_period_name("month", month)
            elif quarter:
                calculated_upload_period = get_period_name("quarter", quarter)
            elif year:
                calculated_upload_period = "April - March"

            

            validation_logger.info(f"[GST][Tally][User Id: {user.id}] Processing Tally data for GSTIN {payload_gstin} from {start_date} to {end_date}")

            validation_logger.info(f"[GST][Tally][User Id: {user.id}] Saving validated PR data to database")
            validate_save_status, unique_return_periods = save_purchase_register_data(input_pr_df, user, gst_info, upload_type)

            validation_logger.info(f"[GST][Tally][User Id: {user.id}] Fetching saved PR data from database for revalidation")
            queryset_from_db = PrData.objects.filter(
                return_period__in=unique_return_periods,
                user_id=user.id,
                user_gst_info_id=gst_info.id,
            ).order_by("-id")
            df_from_db = pd.DataFrame(queryset_from_db.values())

            validation_logger.info("Revalidating PR data")
            revalidate_and_save(user, gst_info, input_pr_df=df_from_db)

            if validate_save_status:

                PrDataTransactions.objects.create(
                    user_gst_info=gst_info,

                    period_start=start_date,
                    period_end=end_date,

                    upload_period=calculated_upload_period,
                    upload_type=upload_type,

                    upload_error_status = False,
                    upload_errors = None
                )

                send_websocket_notification_sync(
                    user_id=user.id,
                    user_gst_info_id=gst_info.id,
                    module="tally_fetch",
                    title="Tally Data Fetch Completed Successfully",
                    message=f"Tally Purchase Register data for {payload_gstin} from {start_date} to {end_date} has been successfully processed and saved. Your GSTR-2B data is now being fetched.",
                    notification_type="success",
                    metadata={"gstin": payload_gstin, "period_start": str(start_date), "period_end": str(end_date), "record_count": len(input_pr_df), "status": "completed"}
                )
                return Response(
                    {"message": "Data Successfully Fetched from tally, respective GSTR-2B data is being fetched."}, status=status.HTTP_200_OK
                )
            else:
                validation_logger.info(f"[GST][Tally][User Id: {user.id}] Validation failed. Sending error notification to client")
                send_websocket_notification_sync(
                    user_id=user.id,
                    user_gst_info_id=gst_info.id,
                    module="tally_fetch",
                    title="Tally Data Upload Failed (Validation Errors)",
                    message=f"Tally Purchase Register data for {payload_gstin} from {start_date} to {end_date} failed validation checks. Please review errors on the Upload Screen.",
                    notification_type="error",
                    metadata={"gstin": payload_gstin, "period_start": str(start_date), "period_end": str(end_date), "status": "validation_failed"}
                )
                return Response(
                    {"message": "Data Fetched from Tally Failed the validation checks. Please view the errors in Upload Screen, fix them and try again."}, status=status.HTTP_200_OK
                )  

        except Exception as e:
            error_message = f"An unexpected error occurred during Tally data processing: {str(e)}"
            validation_logger.error(error_message)

            try:
                PrDataTransactions.objects.create(
                    user_gst_info=gst_info,

                    period_start=start_date,
                    period_end=end_date,

                    upload_period=None,  
                    upload_type=upload_type,

                    upload_error_status = True,
                    upload_errors = f"An unexpected error occurred while processing Tally data. Please connect with support.",  
                )
                validation_logger.info(f"[GST][Tally][User Id: {user.id}] Error logged in PrDataTransactions")
            except Exception as log_e:
                validation_logger.error(f"[GST][Tally][User Id: {user.id}] Failed to log error in PrDataTransactions: {log_e}")

            send_websocket_notification_sync(
                user_id=user.id,
                user_gst_info_id=gst_info.id if gst_info else None,
                module="tally_fetch",
                title="Tally Data Upload Failed (Unexpected Error)",
                message=f"An unexpected error occurred while processing Tally data for {payload_gstin} from {start_date} to {end_date}. Please try again or contact support.",
                notification_type="error",
                metadata={"gstin": payload_gstin, "period_start": str(start_date), "period_end": str(end_date), "status": "failed", "error_type": "UnexpectedError", "details": str(e)}
            )
            return Response(
                {"message": f"Error while fetching data from Tally. Error: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
   