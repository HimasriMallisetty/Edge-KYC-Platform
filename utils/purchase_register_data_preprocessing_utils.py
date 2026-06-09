import logging
import json
import pandas as pd
from apps.gst.constants import TARGET_COLUMNS, EXCEL_COLUMNS
from apps.gst.utils import PurchaseRegisterDataValidator
from apps.gst.models import PrData
from apps.gst.utils import validate_duplicates
validation_logger = logging.getLogger("validations")


class PreprocessPurchaseData():
    def __init__(self, dataframe: pd.DataFrame, user):
        """
        Initializes the PreprocessPurchaseData class with a pandas DataFrame.

        Args:
            dataframe (pd.DataFrame): The input DataFrame to be processed.
        """
        self.dataframe = dataframe
        self.user = user

    def normalise_column_names(self) -> pd.DataFrame:
        """
        Normalizes column names by converting them to lowercase and stripping whitespace.

        Returns:
            pd.DataFrame: The DataFrame with normalized column names.
        """
        self.dataframe.columns = self.dataframe.columns.str.lower().str.strip()
        validation_logger.info(f"[GST][File Upload][User Id: {self.user.id}]Column names normalized to lowercase.")
        return self.dataframe

    def map_column_names(self) -> pd.DataFrame:
        """
        Maps the normalized Excel column names to the target column names.
        It handles cases where not all Excel columns might be present in the DataFrame
        or if there are extra columns.

        Returns:
            pd.DataFrame: The DataFrame with mapped column names according to TARGET_COLUMNS.
        """

        column_mapping = {
            excel_col.lower().strip(): target_col
            for excel_col, target_col in zip(EXCEL_COLUMNS, TARGET_COLUMNS)
        }

        columns_to_rename = {
            col: column_mapping[col]
            for col in self.dataframe.columns
            if col in column_mapping
        }
        self.dataframe.rename(columns=columns_to_rename, inplace=True)
        validation_logger.info("Column names mapped to target names.")


        final_columns = [col for col in TARGET_COLUMNS if col in self.dataframe.columns]
        self.dataframe = self.dataframe[final_columns]
        validation_logger.info("DataFrame columns reordered and unnecessary columns dropped.")

        return self.dataframe
    
from pandas._libs.tslibs.nattype import NaTType
def revalidate_and_save(user, gst_info, document_ids=None, input_pr_df=None):
    try:
        pr_queryset = None

        # Case 1: If DataFrame is provided
        if input_pr_df is not None:
            if input_pr_df.empty:
                validation_logger.info("[GST][Re-validation] Provided input_pr_df is empty.")
                return
            document_ids = input_pr_df['id'].tolist()  # extract IDs for model fetching

        # Case 2: If only document IDs are provided
        elif document_ids is not None:
            pr_queryset = PrData.objects.filter(
                id__in=document_ids,
                user_id=user.id,
                user_gst_info_id=gst_info.id
            )
            if not pr_queryset.exists():
                validation_logger.info(f"[GST][Re-validation] No records found for IDs: {document_ids}")
                return

            input_pr_df = pd.DataFrame(list(pr_queryset.values()))
            if input_pr_df.empty:
                validation_logger.info(f"[GST][Re-validation] Empty DataFrame for IDs: {document_ids}")
                return
        else:
            validation_logger.warning("[GST][Re-validation] Neither document_ids nor input_pr_df provided.")
            return

        # Run validations
        pr_validator = PurchaseRegisterDataValidator()
        validated_pr_df = pr_validator.run_validations(input_pr_df)

        final_df = validate_duplicates(validated_pr_df)

        final_df['validation_errors'] = final_df['validation_errors'].apply(
            lambda x: json.loads(x) if isinstance(x, str) and x.strip().startswith('{') else x
        )

        # Fetch PR model instances as a dictionary {id: instance}
        pr_queryset = PrData.objects.filter(
            id__in=final_df['id'].tolist(),
            user_id=user.id,
            user_gst_info_id=gst_info.id
        )
        pr_obj_map = {obj.id: obj for obj in pr_queryset}

        # Update each record
        for _, row in final_df.iterrows():
            pr_obj = pr_obj_map.get(row['id'])
            if not pr_obj:
                continue  # skip if not found

            for field in final_df.columns:
                if hasattr(pr_obj, field):
                    value = row[field]
                    if isinstance(value, NaTType) or pd.isna(value):
                        value = None
                    setattr(pr_obj, field, value)

            pr_obj.save()

        validation_logger.info(f"[GST][Re-validation] Successfully revalidated and updated records: {document_ids}")

    except Exception as e:
        validation_logger.error(f"[GST][Re-validation] Error while revalidating documents {document_ids}: {str(e)}")
        raise 
