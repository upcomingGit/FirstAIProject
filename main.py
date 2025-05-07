##
# Create Virtual Environment
# pip install pandas llama_cloud_services re
###

import argparse
import re
import pandas as pd
from llama_cloud_services import LlamaParse
from pydantic import ValidationError
from difflib import get_close_matches


class TableExtractor:
    def __init__(self, file_path):
        self.file_path = file_path
        self.lines = self._load_file()

    def _load_file(self):
        """Load file contents into a list of lines."""
        with open(self.file_path, "r", encoding="utf-8") as f:
            return [line.rstrip("\n") for line in f]

    def _safe_float(self, value):
        """Safely convert string to float, handling commas, dashes, and blanks."""
        if not value or value.strip() in ("-", ""):
            return None
        value = value.replace(",", "").strip()
        if value.startswith("(") and value.endswith(")"):
            value = "-" + value[1:-1]
        try:
            return float(value)
        except ValueError:
            return None

    def _fuzzy_match(self, field, candidates):
        """Return closest matching candidate for a field, or None."""
        matches = get_close_matches(field.lower(), [c.lower() for c in candidates], n=1, cutoff=0.7)
        if matches:
            for candidate in candidates:
                if candidate.lower() == matches[0]:
                    return candidate
        return None

    def _extract_table_section(self, lines, header_regex, num_columns):
        """Extracts a table based on a search pattern. Supports fuzzy field matching and dynamic column detection."""
        header_idx, header_line = None, None
        for idx, line in enumerate(lines):
            if re.search(header_regex, line, flags=re.IGNORECASE):
                header_idx = idx
                header_line = line.strip()
                break

        if not header_line:
            return [], [], 0

        headers = [h.strip() for h in header_line.split("|")]
        num_columns = len(headers)
        data_lines = [line.strip() for line in lines[header_idx + 1:] if "|" in line]

        merged_lines = []
        for line in data_lines:
            parts = line.split("|")
            if len(parts) < num_columns:
                if merged_lines:
                    merged_lines[-1] += " " + line
            else:
                merged_lines.append(line)

        records = []
        for row in merged_lines:
            parts = [p.strip() for p in row.split("|")]
            if len(parts) >= num_columns:
                record = dict(zip(headers, parts[:num_columns]))
                for col in record:
                    if "March" in col or "2023" in col or "2024" in col:
                        record[col] = self._safe_float(record[col])
                records.append(record)

        return records, headers, len(headers)

    def extract_common_terms(self, df, common_terms_bs=None, common_terms_cf=None):
        if common_terms_bs and common_terms_cf:
            matched_data = []
            flag_uppercase = 0

            for _, row in df.iterrows():
                temp_value = row["Particulars"]
                if pd.isna(temp_value):
                    particular = str(row["PARTICULARS"]).strip()
                    flag_uppercase = 1
                else:
                    particular = str(temp_value).strip()
                #print(particular)
                if not particular:
                    continue
                # Fuzzy match this row's 'Particulars' against the list of common terms
                match = self._fuzzy_match(particular, common_terms_bs)
                if match:
                    values = row.dropna().tolist()
                    try:
                        matched_data.append({
                            "Particulars": row["Particulars"],
                            "Value_2024": row.iloc[3],  # Assumes 4th column is 2024 value
                            "Value_2023": row.iloc[4]   # Assumes 5th column is 2023 value
                        })
                    except IndexError:
                        # If the row doesn't have enough columns, skip it
                        continue
                else:
                    match = self._fuzzy_match(particular, common_terms_cf)
                    if match:
                        values = row.dropna().tolist()
                        try:
                            if flag_uppercase == 0:
                                matched_data.append({
                                    "Particulars": row["Particulars"],
                                    "Value_2024": row.iloc[5],  # Assumes 4th column is 2024 value
                                    "Value_2023": row.iloc[6]   # Assumes 5th column is 2023 value
                                })
                            else:
                                matched_data.append({
                                    "Particulars": row["PARTICULARS"],
                                    "Value_2024": row.iloc[6],  # Assumes 4th column is 2024 value
                                    "Value_2023": row.iloc[7]   # Assumes 5th column is 2023 value
                                })                                
                        except IndexError:
                            # If the row doesn't have enough columns, skip it
                            continue
            # Create new DataFrame from matched data
            if matched_data:
                result_df = pd.DataFrame(matched_data)
            else:
                result_df = pd.DataFrame(columns=["Particulars", "Value_2024", "Value_2023"])
        else:
            result_df = df
        return result_df



    def extract_combined_tables(self, search_pattern, header_regex=r"Particulars.*\|.*(March|31st).*202[34]", max_capture_lines=400, common_terms_bs=None, common_terms_cf=None):
        start_idx = next((i for i, line in enumerate(self.lines) if re.search(search_pattern, line, flags=re.IGNORECASE)), None)

        if start_idx is None:
            raise ValueError(f"Pattern '{search_pattern}' not found in file.")

        captured_lines = self.lines[start_idx: start_idx + max_capture_lines]

        # Extract balance sheet
        bs_records, bs_headers, bs_col_count = self._extract_table_section(captured_lines, header_regex, num_columns=0)

        # Extract cash flow (if present)
        cf_idx = next((i for i, line in enumerate(captured_lines) if re.search(r"# Consolidated Cash Flow Statement", line, flags=re.IGNORECASE)), None)
        cf_records, _, _ = [], [], 0

        if cf_idx is None:
            cf_idx = next((i for i, line in enumerate(captured_lines) if re.search(r"# Consolidated Statement of Cash Flow", line, flags=re.IGNORECASE)), None)

        if cf_idx is not None:
            cf_lines = captured_lines[cf_idx:]
            cf_records, _, _ = self._extract_table_section(cf_lines, header_regex, num_columns=0)

        all_records = bs_records + cf_records
        df = pd.DataFrame(all_records)
        #df.to_csv("output_tinna.csv", index=False)
        df2 = self.extract_common_terms(df, common_terms_bs, common_terms_cf)

        return df2


def parse_pdf_to_markdown(input_pdf_path, output_md_path):
    """Parse PDF using LlamaParse and save markdown output."""

    parser = LlamaParse(
        api_key="llx-QjNSddwuomeFmGWT0na2HAfRsZiA4Jf0x9P0hsiMKNlc7Hfu",  # hard-coded API key
        invalidate_cache=True,
        ignore_errors=True,
        num_workers=4,
        verbose=True,
        language="en",
        result_type="markdown",
        skip_diagonal_text=True,
        disable_image_extraction=True,
        strict_mode_image_extraction=False,
    )

    try:
        result = parser.parse(input_pdf_path)
        with open(output_md_path, "w", encoding="utf-8") as f:
            f.write("Welcome to Ankur's LLM program\n\n")
            for page in result.pages:
                f.write(str(page.md))
    except ValidationError as ve:
        print("Validation error occurred while parsing the PDF!")
        print(ve)
    except Exception as e:
        print("Unexpected error during parsing!")
        print(e)


def main():
    parser = argparse.ArgumentParser(description="Extract tables from a parsed markdown generated from a PDF.")
    parser.add_argument("input_pdf", type=str, help="Path to the input PDF file")
    parser.add_argument("output_md", type=str, help="Path to output markdown file")
    args = parser.parse_args()

    common_terms_bs = [
    "Assets"
    ,"Non-current Assets"
    ,"Property, Plant and Equipment"
    ,"Capital Work-in-Progress"
    ,"Right of Use Assets"
    ,"Financial Assets"
    ,"Investments"
    ,"Other Financial Assets"
    ,"Current Assets"
    ,"Inventories"
    ,"Trade Receivables"
    ,"Cash and Cash Equivalents"
    ,"Loans"
    ,"Other Current Assets"
    ,"Total Assets"
    ,"Equity and Liabilities"
    ,"Equity"
    ,"Equity Share Capital"
    ,"Other Equity"
    ,"Total Equity"
    ,"Liabilities"
    ,"Non-current Liabilities"
    ,"Financial Liabilities"
    ,"Borrowings"
    ,"Lease Liabilities"
    ,"Provisions"
    ,"Deferred Tax Liabilities (Net)"
    ,"Total Non-current Liabilities"
    ,"Current Liabilities"
    ,"Trade Payables"
    ,"Total Outstanding Dues of Micro Enterprises and Small Enterprises"
    ,"Total Outstanding Dues of Creditors Other Than Micro Enterprises and Small Enterprises"
    ,"Other Financial Liabilities"
    ,"Other Current Liabilities"
    ,"Current Tax Liabilities (Net)"
    ,"Total Current Liabilities"
    ,"Total Equity and Liabilities"
    ,"Revenue from Operations"
    ,"Other Income"
    ,"Total Income"
    ,"Expenses"
    ,"Cost of Materials Consumed"
    ,"stock in trade"
    ,"Employee Benefits Expense"
    ,"Finance Costs"
    ,"Depreciation and Amortisation Expense"
    ,"Other Expenses"
    ,"Total Expenses"
    ,"Profit Before Tax"
    ,"Tax Expense"
    ,"Current Tax"
    ,"Deferred Tax"
    ,"Total Tax Expense"
    ,"Profit for the Year"
    ,"Other Comprehensive Income"
    ,"Total Comprehensive Income"
    ,"Earnings Per Equity Share"
    ,"Basic (Rs.)"
    ,"Diluted (Rs.)"]
    common_terms_cf = [
    "Cash Flows from Operating Activities"
    ,"Profit Before Tax"
    ,"Depreciation and Amortisation Expense"
    ,"Finance Cost"
    ,"Interest Received"
    ,"Operating Profit Before Working Capital Changes"
    ,"Inventories"
    ,"Trade Receivables"
    ,"Other Financial Assets"
    ,"Other Assets"
    ,"Trade Payables"
    ,"Other Financial Liabilities"
    ,"Other Liabilities"
    ,"Provisions"
    ,"Cash Flows Generated from Operations"
    ,"Income Tax Paid (Net of Refunds)"
    ,"Net Cash Flow Generated from Operating Activities"
    ,"Cash Flows from Investing Activities"
    ,"Purchase of Property, Plant and Equipment"
    ,"Proceeds from Sale of Property, Plant and Equipment"
    ,"Net Cash Flows Used in Investing Activities"
    ,"Cash Flows from Financing Activities"
    ,"Proceeds from Long Term Borrowings"
    ,"Repayment of Long Term Borrowings"
    ,"Dividend Paid"
    ,"Interest Paid"
    ,"Net Cash Flows Used in Financing Activities"
    ,"Net Increase/Decrease in Cash and Cash Equivalents"
    ,"Cash and Cash Equivalents at the Beginning of the Year"
    ,"Cash and Cash Equivalents at the End of the Year"]

    # Step 1: Parse PDF to Markdown
    #parse_pdf_to_markdown(args.input_pdf, args.output_md)

    # Step 2: Extract Tables
    extractor = TableExtractor(args.output_md)
    df = extractor.extract_combined_tables(search_pattern=r"# Consolidated Balance Sheet", common_terms_bs=common_terms_bs, common_terms_cf=common_terms_cf)

    print(df.to_string())
    output_file_name = args.output_md[:-2] + "csv"
    df.to_csv(output_file_name, index=False)


if __name__ == "__main__":
    main()
