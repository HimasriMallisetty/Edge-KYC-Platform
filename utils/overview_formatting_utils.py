from django.db.models import Q, Sum, F, Value, DecimalField

from apps.gst.models import TimeRange

def check_data_status(request_body_year):
    exists = TimeRange.objects.filter(
        Q(FY=request_body_year) & Q(status_reco=2)
    ).exists()
    return exists


def calculate_summary(queryset, source):
    total = (
        queryset.aggregate(
            total=Sum(f"Total_tax_{source}", output_field=DecimalField())
        )["total"]
        or 0
    )

    match = (
        queryset.filter(Category="Match").aggregate(
            total=Sum(F(f"IGST_{source}"), output_field=DecimalField())
            + Sum(F(f"CGST_{source}"), output_field=DecimalField())
            + Sum(F(f"SGST_{source}"), output_field=DecimalField())
        )["total"]
        or 0
    )

    value_mismatch = (
        queryset.filter(Category="Value Mismatch").aggregate(
            total=Sum(F(f"IGST_{source}"), output_field=DecimalField())
            + Sum(F(f"CGST_{source}"), output_field=DecimalField())
            + Sum(F(f"SGST_{source}"), output_field=DecimalField())
        )["total"]
        or 0
    )

    missing_in_2b = (
        queryset.filter(Category="Missing in 2B").aggregate(
            total=Sum(F(f"IGST_{source}"), output_field=DecimalField())
            + Sum(F(f"CGST_{source}"), output_field=DecimalField())
            + Sum(F(f"SGST_{source}"), output_field=DecimalField())
        )["total"]
        or 0
    )

    missing_in_pr = (
        queryset.filter(Category="Missing in PR").aggregate(
            total=Sum(F(f"IGST_{source}"), output_field=DecimalField())
            + Sum(F(f"CGST_{source}"), output_field=DecimalField())
            + Sum(F(f"SGST_{source}"), output_field=DecimalField())
        )["total"]
        or 0
    )

    return {
        "Total": f"{total:.2f}",
        "Match": f"{match:.2f}",
        "Value Mismatch": f"{value_mismatch:.2f}",
        "Missing in 2B": f"{missing_in_2b:.2f}",
        "Missing in PR": f"{missing_in_pr:.2f}",
    }


def get_Table_values(queryset, filtering_return_periods):
    # print(filtering_return_periods)
    categories = [
        ("Total 2B", "Total No. of Docs present in 2B (B2B, CDNR, B2BA, CONRA)", None),
        ("Total PR", "Total No. of Docs present in PR", None),
        (
            "Match",
            "All key fields match, including Supplier GSTIN, Invoice Number, and numeric values (within default tolerance)",
            None,
        ),
        (
            "Value Mismatch",
            "Supplier GSTIN and Invoice Number match, but differences exist in numeric fields beyond default tolerance",
            None,
        ),
        (
            "Missing in 2B",
            "Invoice exists in PR but is not found in GSTR-2B",
            "Match the invoices on linking screen using our suggestions.",
        ),
        (
            "Missing in PR",
            "Invoice exists in GSTR-2B but is not found in PR",
            "Match the invoices on linking screen using our suggestions.",
        ),
    ]

    table_values = []
    for category, description, action_suggestion in categories:
        message_2b_draft = None
        message_pr_draft = None
        if category == "Total 2B":
            no_of_docs_2b_self = queryset.filter(
                Period_2B__in=filtering_return_periods
            ).count()
            # print("no_of_docs_2b_self", no_of_docs_2b_self)

            no_of_docs_2b_others = (
                queryset.exclude(Period_2B__in=filtering_return_periods)
                .exclude(Period_2B__isnull=True)
                .exclude(Period_2B="")
                .count()
            )
            # print("no_of_docs_2b_others", no_of_docs_2b_others)

            no_of_docs_2b = no_of_docs_2b_self + no_of_docs_2b_others
            no_of_docs_pr = 0

            tax = queryset.aggregate(total=Sum("Total_tax_2B"))["total"] or 0
            if no_of_docs_2b_others > 0:
                message_2b_draft = f"Total 2B count might differ due to the Match of PR documents with other period 2B documents. (Current period:{no_of_docs_2b_self} , Other period: {no_of_docs_2b_others})"

        elif category == "Total PR":
            no_of_docs_pr_self = queryset.filter(
                Period_PR__in=filtering_return_periods
            ).count()

            no_of_docs_pr_others = (
                queryset.exclude(Period_PR__in=filtering_return_periods)
                .exclude(Period_PR__isnull=True)
                .exclude(Period_PR="")
                .count()
            )

            no_of_docs_2b = 0
            no_of_docs_pr = no_of_docs_pr_self + no_of_docs_pr_others

            tax = queryset.aggregate(total=Sum("Total_tax_PR"))["total"] or 0
            if no_of_docs_pr_others > 0:
                message_pr_draft = f"Total PR count might differ due to the Match of 2B documents with other period PR documents. (Current period:{no_of_docs_pr_self} , Other period: {no_of_docs_pr_others})"

        else:
            no_of_docs_2b = (
                queryset.filter(Category=category)
                .exclude(Transaction_id_2b__isnull=True)
                .count()
            )
            no_of_docs_pr = (
                queryset.filter(Category=category)
                .exclude(Transaction_id_pr__isnull=True)
                .count()
            )
            tax = (
                queryset.filter(Category=category).aggregate(
                    total=Sum("Total_Tax_Difference")
                )["total"]
                or 0
            )

        table_values.append(
            {
                "Category": category,
                "Description": description,
                "No_of_docs_2B": no_of_docs_2b,
                "No_of_docs_PR": no_of_docs_pr,
                "Tax": round(tax, 2),
                "Action_Suggestion": action_suggestion,
                "message_2B": message_2b_draft,
                "message_PR": message_pr_draft,
            }
        )

    return table_values

