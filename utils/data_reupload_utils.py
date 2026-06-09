from apps.gst.models import TimeRange

def get_reupload_status(user, gst_info, fy, month=None, quarter=None):
    filters = {
        'FY': fy,
        'user_id': user.id,
        'user_gst_info_id': gst_info.id,
    }

    if month is not None:
        filters['Month'] = month
        queryset = TimeRange.objects.filter(**filters)
        return queryset.filter(status_PR=1).exists()

    elif quarter is not None:
        filters['Quarter'] = quarter
        queryset = TimeRange.objects.filter(**filters)
        return queryset.filter(status_PR=1).exists()

    else:
        # Only FY provided
        queryset = TimeRange.objects.filter(**filters)
        return queryset.filter(status_PR=1).exists()
    
