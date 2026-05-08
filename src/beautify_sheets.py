import os
import sys

from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from services.sheets_service import SheetsService

load_dotenv()


def beautify():
    service = SheetsService()
    if not service.spreadsheet:
        print("Could not connect to Spreadsheet.")
        return

    # Professional Color Palette (Normalized RGB 0-1)
    COLOR_HEADER_BG = {"red": 0.07, "green": 0.18, "blue": 0.29}  # Deep Navy
    COLOR_HEADER_TEXT = {"red": 1.0, "green": 1.0, "blue": 1.0}  # White

    sheets = service.spreadsheet.worksheets()
    requests = []

    for sheet in sheets:
        s_id = sheet.id

        # 1. Basic formatting for all sheets
        requests.append(
            {
                "repeatCell": {
                    "range": {"sheetId": s_id, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": COLOR_HEADER_BG,
                            "horizontalAlignment": "CENTER",
                            "verticalAlignment": "MIDDLE",
                            "textFormat": {
                                "foregroundColor": COLOR_HEADER_TEXT,
                                "bold": True,
                                "fontSize": 10,
                            },
                            "borders": {
                                "bottom": {
                                    "style": "SOLID_MEDIUM",
                                    "color": COLOR_HEADER_TEXT,
                                }
                            },
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,horizontalAlignment,verticalAlignment,textFormat,borders)",  # noqa: E501
                }
            }
        )

        # 2. Freeze Header
        requests.append(
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": s_id,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            }
        )

        # 3. Auto-resize Columns
        requests.append(
            {
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": s_id,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": 26,
                    }
                }
            }
        )

        # 4. Alternating Row Colors (Banding)
        # We wrap this in a separate try-block logic usually, but here we'll just add it.  # noqa: E501
        # To avoid error if exists, we could delete first, but gspread doesn't have a simple "delete all bandings".  # noqa: E501
        # We'll skip banding for now and use repeatCell with a light color for the data area.  # noqa: E501
        requests.append(
            {
                "repeatCell": {
                    "range": {"sheetId": s_id, "startRowIndex": 1, "endRowIndex": 1000},
                    "cell": {
                        "userEnteredFormat": {
                            "verticalAlignment": "MIDDLE",
                            "textFormat": {"fontSize": 9},
                        }
                    },
                    "fields": "userEnteredFormat(verticalAlignment,textFormat)",
                }
            }
        )

    # 5. SPECIAL DASHBOARD STYLING
    try:
        dash = service.spreadsheet.worksheet("Dashboard")
        d_id = dash.id

        # Make Metric names bold and KPI values large
        requests.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": d_id,
                        "startColumnIndex": 0,
                        "endColumnIndex": 1,
                    },
                    "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 11}}},
                    "fields": "userEnteredFormat(textFormat)",
                }
            }
        )
        requests.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": d_id,
                        "startColumnIndex": 1,
                        "endColumnIndex": 2,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {
                                "bold": True,
                                "fontSize": 12,
                                "foregroundColor": {
                                    "red": 0.1,
                                    "green": 0.5,
                                    "blue": 0.2,
                                },
                            },
                            "horizontalAlignment": "CENTER",
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,horizontalAlignment)",
                }
            }
        )
    except Exception:
        pass

    # Execute batch update
    if requests:
        try:
            service.spreadsheet.batch_update({"requests": requests})
            print("Successfully applied professional aesthetics to all sheets!")
        except Exception as e:
            print(f"Error applying formatting: {e}")


if __name__ == "__main__":
    beautify()
