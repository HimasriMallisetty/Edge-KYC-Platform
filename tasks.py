import os
import pytz
from datetime import datetime

from django.utils.timezone import now

from apps.gst.models import UserGstInfo
from apps.gst.utils import refresh_gst_token

def refresh_token():
    """Refresh GST tokens for all users."""
    # Determine log file path (in the same directory as the script)
    log_file_path = os.path.join(os.path.dirname(__file__), 'cronlog.txt')

    gst_info_list = UserGstInfo.objects.all()

    if not gst_info_list.exists():
        log_message = "No GST information found to refresh."        
        # Log to file
        with open(log_file_path, 'a') as log_file:
            log_file.write(f"[{datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S %Z')}] {log_message}\n")
        
        return

    for gst_info in gst_info_list:
        with open(log_file_path, 'a') as log_file:
            log_file.write(f"[>> >> >> {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S %Z')} For User: {gst_info.user}] \n")
        old_token = gst_info.gst_token  
        new_token, code = refresh_gst_token(old_token)
        
        new_token_log = f"New token in tasks: {new_token}"
        
        # Log new token attempt
        with open(log_file_path, 'a') as log_file:
            log_file.write(f"[{datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S %Z')}] {new_token_log}\n")

        if new_token:
            gst_info.gst_token = new_token 
            gst_info.refreshed_at = now()  
            gst_info.save(update_fields=['gst_token', 'refreshed_at'])  
            
            if code == 200:
                success_log = f"Token refreshed for GSTIN: {gst_info.gstin}"
            else:
                success_log = f"Token failed to refresh for GSTIN: {gst_info.gstin}"
            
            # Log successful token refresh
            with open(log_file_path, 'a') as log_file:
                log_file.write(f"[{datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S %Z')}] {success_log}\n")
        else:
            failure_log = f"Error While Refreshing Token: {gst_info.gstin}"
            
            # Log token refresh failure
            with open(log_file_path, 'a') as log_file:
                log_file.write(f"[{datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S %Z')}] {failure_log}\n")
