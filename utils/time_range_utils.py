from datetime import datetime

from apps.gst.models import TimeRange

# * Upon User account creatation this will insert the basic template of TimeRange of each month for each user.
def insert_time_range_data(user, user_gst_information):
    try:
        current_year = datetime.now().year
        current_month = datetime.now().month

        records_to_create = []

        for year in range(2017, current_year + 1):
            start_month = 7 if year == 2017 else 1

            end_month = current_month if year == current_year else 12

            for month in range(start_month, end_month + 1):
                quarter = ((month - 4) % 12) // 3 + 1
                fy = f"{year}-{year+1}" if month >= 4 else f"{year-1}-{year}"

                records_to_create.append(
                    TimeRange(
                        user=user,
                        user_gst_info=user_gst_information,
                        Month=month,
                        Year=year,
                        Quarter=quarter,
                        FY=fy,
                        status_PR=False,
                        status_2B=False,
                        status_reco=0,
                        status_upload=True,
                        no_of_doc_PR=0,
                        no_of_doc_2B=0,
                        tax_difference=0.0,
                        itc_PR=0.0,
                        itc_2B=0.0,
                    )
                )

        TimeRange.objects.bulk_create(records_to_create)
    except Exception as e:
        print(e)


# * Every month we must add the prev month into TimeRange for existing members
def update_time_range_data():
    """
    after each month : need to update a row
    """
    pass