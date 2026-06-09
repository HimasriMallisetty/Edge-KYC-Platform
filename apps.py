import os
import pytz
import time
from datetime import datetime

from django.apps import AppConfig
from django.core.checks import register, Tags
from django.db import connections, OperationalError

class KycConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.gst'

    def ready(self):
        """
        Ensures the database is available before scheduling tasks.
        Avoids querying the database too early during app initialization.
        """

        @register(Tags.database)
        def check_database_ready(app_configs, **kwargs):
            self.schedule_tasks()
            return []

    def schedule_tasks(self):
        """
        Attempts to schedule the `refresh_token` task only if the database is ready.
        Retries up to 5 times if the database is not available.
        """
        # Determine log file path (in the same directory as the script)
        log_file_path = os.path.join(os.path.dirname(__file__), 'cronlog.txt')

        max_retries = 5  
        retry_delay = 2  

        for attempt in range(max_retries):
            try:
                connections['default'].ensure_connection()
                
                # Log successful database connection
                with open(log_file_path, 'a') as log_file:
                    log_file.write(f"{20*'*'}\n")
                    log_file.write(f"[{datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S %Z')}] Database connection successful.\n")
                
                break  # Database is ready
            except OperationalError:
                if attempt < max_retries - 1:
                    error_msg = f"Database not ready. Retrying in {retry_delay} seconds..."
                    
                    
                    # Log database connection retry
                    with open(log_file_path, 'a') as log_file:
                        log_file.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {error_msg}\n")
                    
                    time.sleep(retry_delay)
                else:
                    error_msg = "Database is not ready after multiple attempts. Skipping task scheduling."
                    
                    
                    # Log final database connection failure
                    with open(log_file_path, 'a') as log_file:
                        log_file.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {error_msg}\n")
                    
                    return  

        from django_q.models import Schedule

        task_path = 'apps.gst.tasks.refresh_token'
        try:
            if not Schedule.objects.filter(func=task_path).exists():
                Schedule.objects.create(
                    func=task_path,
                    schedule_type=Schedule.CRON,
                    cron="0 */5 * * *",  # Run every 5 hours
                    repeats=-1  
                )
                success_msg = "Scheduled refresh_token task to run every 3 minutes"
                
                
                # Log task scheduling success
                with open(log_file_path, 'a') as log_file:
                    log_file.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {success_msg}\n")
                
                pass
            else:
                existing_msg = "refresh_token task is already scheduled."
                
                
                # Log existing task
                with open(log_file_path, 'a') as log_file:
                    log_file.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {existing_msg}\n")
        except Exception as e:
            error_msg = f"Failed to access database. Error: {str(e)}"
            
            
            # Log database access failure
            with open(log_file_path, 'a') as log_file:
                log_file.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {error_msg}\n")
            
            pass