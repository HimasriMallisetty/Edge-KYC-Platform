import calendar
import pandas as pd
from datetime import datetime, date

def get_financial_year_available_months(financial_year):
    start_year, end_year = map(int, str(financial_year).split("-"))
    months = []
    for month in range(4, 13):
        months.append([month, start_year])
    for month in range(1, 4):
        months.append([month, end_year])
    return months


def format_date(date_str):
    if not date_str:
        return None
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.strftime("%d-%m-%Y")
    except Exception as e:
        # print(e)
        return date_str


def convert_to_date(date_input):
    if pd.isna(date_input):
        return None
    if isinstance(date_input, datetime):
        return date_input.date()
    elif isinstance(date_input, date):
        return date_input  # Already a date object
    elif isinstance(date_input, str) and date_input.strip():
        for fmt in ("%d-%m-%Y", "%Y-%m-%d"): # Supports parsing both formats
            try:
                return datetime.strptime(date_input.strip(), fmt).date()
            except ValueError:
                continue
    return None


def get_month_quarter_year_from_date(start_date_str, end_date_str):
    """
    Determines the month, financial quarter, and financial year based on a given date range.
    Financial year starts from April 1st and ends on March 31st of the next calendar year.

    Args:
        start_date_str (str): The start date in 'YYYY-MM-DD' format.
        end_date_str (str): The end date in 'YYYY-MM-DD' format.

    Returns:
        tuple: A tuple containing (month, quarter, financial_year_str).
               - month: Integer if the range is a single full calendar month, None otherwise.
               - quarter: Integer (1-4 for financial year) if the range is a single full financial quarter, None otherwise.
               - financial_year_str: String in "YYYY-YYYY" format if the range is within a single financial year
                                     or covers a full financial year, None otherwise.
    """

    # Helper to get the last day of a month
    def get_last_day_of_month(year, month):
        return calendar.monthrange(year, month)[1]

    # Helper to determine the financial year from a calendar year and month
    def get_financial_year(year, month):
        if 1 <= month <= 3:  # Jan, Feb, Mar belong to the previous calendar year's financial year
            return year - 1
        else:  # Apr to Dec belong to the current calendar year's financial year
            return year

    # Helper to get the financial quarter from a calendar month
    def get_financial_quarter(month):
        if 4 <= month <= 6:   # April, May, June
            return 1
        elif 7 <= month <= 9:   # July, August, September
            return 2
        elif 10 <= month <= 12: # October, November, December
            return 3
        elif 1 <= month <= 3:   # January, February, March
            return 4
        return None # Should not happen with valid month input

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() # Ensure it's a date object
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()   # Ensure it's a date object
    except ValueError:
        # Handle invalid date format
        return None, None, None

    # Error handling for start_date after end_date
    if start_date > end_date:
        return None, None, None

    start_year_cal, start_month_cal, start_day_cal = start_date.year, start_date.month, start_date.day
    end_year_cal, end_month_cal, end_day_cal = end_date.year, end_date.month, end_date.day

    # Determine the financial year for start and end dates
    start_fin_year = get_financial_year(start_year_cal, start_month_cal)
    end_fin_year = get_financial_year(end_year_cal, end_month_cal)

    # Initialize return values
    month_result = None
    quarter_result = None
    financial_year_str = None

    # Case 1: Check if the range covers an entire Financial Year (April 1st to March 31st of next year)
    if (start_month_cal == 4 and start_day_cal == 1 and  # Starts on April 1st
        end_month_cal == 3 and end_day_cal == get_last_day_of_month(end_year_cal, 3) and # Ends on March 31st
        get_financial_year(start_year_cal, start_month_cal) == get_financial_year(end_year_cal, end_month_cal -1) # Check if start_fin_year matches end_fin_year
       ):
        # A full financial year spans across calendar years, so the end_fin_year will be the same as start_fin_year.
        # We need to make sure the end_date is indeed in the NEXT calendar year's March.
        if end_year_cal == start_year_cal + 1 :
            financial_year_str = f"{start_fin_year}-{start_fin_year + 1}"
            return None, None, financial_year_str

    # Case 2: Check if the range covers a single full calendar month
    # This remains the same as it's about a calendar month, not a financial month.
    # We also assign financial year if it's within the same financial year.
    if (start_year_cal == end_year_cal and start_month_cal == end_month_cal and
        start_day_cal == 1 and end_day_cal == get_last_day_of_month(start_year_cal, start_month_cal)):
        
        # If it's a full calendar month within a single financial year
        if start_fin_year == end_fin_year:
            financial_year_str = f"{start_fin_year}-{start_fin_year + 1}"
            return start_month_cal, get_financial_quarter(start_month_cal), financial_year_str

    # Case 3: Check if the range covers a single full financial quarter
    if start_fin_year == end_fin_year: # Must be within the same financial year
        q_start = get_financial_quarter(start_month_cal)
        q_end = get_financial_quarter(end_month_cal)

        if q_start is not None and q_start == q_end:
            # Define start and end months for each financial quarter
            financial_quarter_boundaries = {
                1: (4, 6),   # Q1: Apr-Jun
                2: (7, 9),   # Q2: Jul-Sep
                3: (10, 12), # Q3: Oct-Dec
                4: (1, 3)    # Q4: Jan-Mar
            }
            
            q_start_month_cal, q_end_month_cal = financial_quarter_boundaries[q_start]

            # Adjust calendar year for Q4 (Jan-Mar) for boundary checks
            effective_start_year = start_year_cal
            effective_end_year = end_year_cal
            if q_start == 4: # If it's Q4 (Jan-Mar), the start month is in the previous financial year's calendar year
                effective_start_year = start_fin_year + 1 # The calendar year for Jan-Mar
                effective_end_year = start_fin_year + 1

            # Check if start_date is the first day of the quarter's first month
            is_start_of_quarter = (start_month_cal == q_start_month_cal and start_day_cal == 1)

            # Check if end_date is the last day of the quarter's last month
            is_end_of_quarter = (end_month_cal == q_end_month_cal and
                                 end_day_cal == get_last_day_of_month(effective_end_year, q_end_month_cal))
            
            if is_start_of_quarter and is_end_of_quarter:
                financial_year_str = f"{start_fin_year}-{start_fin_year + 1}"
                return None, q_start, financial_year_str
    
    # Default case: if not a whole financial year, full calendar month, or full financial quarter.
    # Return financial year if the range is fully contained within a single financial year.
    if start_fin_year == end_fin_year:
        financial_year_str = f"{start_fin_year}-{start_fin_year + 1}"
        return None, None, financial_year_str
    
    # If the range spans across financial years or is otherwise unidentifiable as a specific period
    return None, None, None


def get_start_end_period(year, quarter=None, month=None):
    start_year, end_year = map(int, year.split("-"))

    financial_year_months = {
        1: (4, 6),  # Q1: April to June
        2: (7, 9),  # Q2: July to September
        3: (10, 12),  # Q3: October to December
        4: (1, 3),  # Q4: January to March
    }

    if month:
        month = int(month)
        year_to_use = start_year if month >= 4 else end_year
        start_date = f"{year_to_use}-{month:02d}-01"

        # Determine the last day of the month
        if month in [1, 3, 5, 7, 8, 10, 12]:
            end_day = 31
        elif month in [4, 6, 9, 11]:
            end_day = 30
        else:  # February
            end_day = 29 if year_to_use % 4 == 0 else 28

        end_date = f"{year_to_use}-{month:02d}-{end_day:02d}"

    elif quarter:
        quarter = int(quarter)
        start_month, end_month = financial_year_months[quarter]

        year_start = start_year if start_month >= 4 else end_year
        year_end = start_year if end_month >= 4 else end_year

        start_date = f"{year_start}-{start_month:02d}-01"
        end_day = 30 if end_month in [4, 6, 9, 11] else 31
        end_date = f"{year_end}-{end_month:02d}-{end_day:02d}"

    else:  # Full financial year
        start_date = f"{start_year}-04-01"
        end_date = f"{end_year}-03-31"

    return start_date, end_date


def get_return_periods(year, quarter=None, month=None):
    start_year, end_year = map(int, year.split("-"))

    financial_year_months = {1: (4, 6), 2: (7, 9), 3: (10, 12), 4: (1, 3)}

    return_periods = []

    if month:
        month = int(month)
        year_to_use = start_year if month >= 4 else end_year
        return_periods.append(f"{month:01d}{year_to_use}")
        return_periods.append(f"{month:02d}{year_to_use}")

    elif quarter:
        quarter = int(quarter)
        start_month, end_month = financial_year_months[quarter]

        for m in range(start_month, end_month + 1):
            year_to_use = start_year if m >= 4 else end_year
            return_periods.append(f"{m:01d}{year_to_use}")
            return_periods.append(f"{m:02d}{year_to_use}")

    else:
        for m in range(4, 13):
            return_periods.append(f"{m:01d}{start_year}")
            return_periods.append(f"{m:02d}{start_year}")
        for m in range(1, 4):
            return_periods.append(f"{m:01d}{end_year}")
            return_periods.append(f"{m:02d}{end_year}")

    return return_periods


def get_period_name(period_type, value):
    month_mapping = {
        1: "January",
        2: "February",
        3: "March",
        4: "April",
        5: "May",
        6: "June",
        7: "July",
        8: "August",
        9: "September",
        10: "October",
        11: "November",
        12: "December",
    }

    quarter_mapping = {
        1: "April - June",
        2: "July - September",
        3: "October - December",
        4: "January - March",
    }

    if period_type.lower() == "month":
        return month_mapping.get(int(value))
    elif period_type.lower() == "quarter":
        return quarter_mapping.get(int(value))



def extract_month_year(date_str):
    try:
        date_obj = datetime.strptime(date_str, "%d-%m-%Y")
        return f"{date_obj.month}-{date_obj.year}"  # Ex: "04-2024"
    except ValueError:
        return None


def calculateFY(return_period):
    try:
        if not return_period.isdigit():
            return_period, _ = return_period.split(".")

        return_period = str(return_period).strip()

        if pd.isna(return_period):
            return None

        return_period = return_period.zfill(6)
        month = return_period[:2]
        year = return_period[2:]

        fy = year if int(month) > 3 else str(int(year) - 1)

        return f"{fy} - {int(fy)+1}"
    except Exception as e:
        return None


   
def calculate_upload_type(data):
    # print("\n>> calculateUploadType Function has been hit.")
    total_dates = data["accounting date"]
    unique_months = []
    data["accounting date"] = pd.to_datetime(data["accounting date"], format="%d-%m-%Y")
    unique_months = data["accounting date"].dt.strftime("%B").unique()

    # print("     -> List of Unique Months: ", unique_months)
    if len(unique_months) == 1:
        # print("     -> Returning: ", unique_months[0])
        # print("\n")
        return unique_months[0]
    else:
        # print("     -> Returning: ", f"{unique_months[0]} - {unique_months[-1]}")
        # print("\n")
        return f"{unique_months[0]} - {unique_months[-1]}"
