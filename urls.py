from django.urls import path

from apps.gst.views import (
    UserAuthDetails,
    UploadPR,
    PrTransactions,
    TimeRangeAPI,
    ViewPrData,
    PerformReco,
    PopupSummary,
    DeleteDocument,
    AddDocument,
    RecoSupplierView,
    RecoInvoiceView,
    RecoOverview,
    RecoDashboard,
    DownloadDocuments,
    LinkInvoices,
    DelinkInvoices,
    GetLinkingSuggestions,
    LinkHistory,
    DelinkHistory,
    Refetch2B,
    DownloadRecoDetailedReport,
    DownloadRecoOverviewReport,
    SelectedDocumentsForMailing,
    ProcessDataFromTally,
    DraftMail,
    NotificationsList,
    NotificationMarkRead,
    ValidateAndSave
)

app_name = "gst"

urlpatterns = [ 
    path('user-auth-details/', UserAuthDetails.as_view(), name='user_auth_details'),
    path('time-range/', TimeRangeAPI.as_view(), name='time_range'),

    path('validate-pr/', UploadPR.as_view(), name='validate_pr'),
    path('pr-transactions/', PrTransactions.as_view(), name='pr_transactions'),
    path('view-pr-data/', ViewPrData.as_view(), name='view_pr_data'),
    path('validate-and-save/', ValidateAndSave.as_view(), name="validate_and_save"),
    path('delete-document/', DeleteDocument.as_view(), name='delete_document'),
    path('add-document/', AddDocument.as_view(), name='add-document'),

    path('popup-summary/', PopupSummary.as_view(), name='pr_popup_summary'),
    path('perform-reco/', PerformReco.as_view(), name='perform_reco'),
    
    path('reco-supplier-view/', RecoSupplierView.as_view(), name='reco_supplier_view'),
    path('reco-invoice-view/', RecoInvoiceView.as_view(), name='reco_invoice_view'),
    path('reco-overview/', RecoOverview.as_view(), name='reco_overview'), 
    path('reco-dashboard/', RecoDashboard.as_view(), name='reco_dashboard'),

    path('link-invoices/', LinkInvoices.as_view(), name='link_invoices'), 
    path('delink-invoices/', DelinkInvoices.as_view(), name='delink_invoices'),
    path('get-linking-suggestions/', GetLinkingSuggestions.as_view(), name='get_linking_suggestions'), 
    path('link-history/', LinkHistory.as_view(), name='link_history'),
    path('delink-history/', DelinkHistory.as_view(), name='delink_history'), 

    path('refetch-2b/', Refetch2B.as_view(), name='refetch_2b'),

    path('download-documents/', DownloadDocuments.as_view(), name='download_documents'),
    path('reco-detailed-report/', DownloadRecoDetailedReport.as_view(), name='download_reco_detailed_report'),
    path('reco-overview-report/', DownloadRecoOverviewReport.as_view(), name='download_reco_overview_report'),   
    
    path('documents-for-mailing/', SelectedDocumentsForMailing.as_view(), name="documents_for_mailing"),
    path('draft-mails/', DraftMail.as_view(), name="draft_mails"),
    
    path('process-tally-data/', ProcessDataFromTally.as_view(), name='process_tally_data'),
    
    path('notifications/', NotificationsList.as_view(), name='notification_api'),
    path('notifications/mark-as-read/', NotificationMarkRead.as_view(), name='mark_as_read_notifications'),
    
]

