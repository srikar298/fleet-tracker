import os
import sys
from typing import Any

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from services.sheets_service import SheetsService

def beautify() -> None:
    service = SheetsService()
    if not service.spreadsheet:
        print("Could not connect to Spreadsheet.")
        return

    worksheets = service.spreadsheet.worksheets()
    
    requests: list[dict[str, Any]] = []
    
    for ws in worksheets:
        sheet_id = ws.id
        print(f"Formatting {ws.title}...")
        
        # 1. Freeze first row
        requests.append({
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {
                        "frozenRowCount": 1
                    }
                },
                "fields": "gridProperties.frozenRowCount"
            }
        })
        
        # 2. Format Header (Row 1)
        # Background: Dark Grey (0.2, 0.2, 0.2), Text: White, Bold: True, Alignment: Center
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.1, "green": 0.1, "blue": 0.1},
                        "horizontalAlignment": "CENTER",
                        "textFormat": {
                            "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                            "fontSize": 10,
                            "bold": True
                        }
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
            }
        })
        
        # 3. Alternating Row Colors (Subtle)
        # We can't easily do this with simple repeatCell without knowing row count
        # But we can set a default font for the whole sheet
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 1
                },
                "cell": {
                    "userEnteredFormat": {
                        "verticalAlignment": "MIDDLE",
                        "textFormat": {
                            "fontSize": 9
                        }
                    }
                },
                "fields": "userEnteredFormat(verticalAlignment,textFormat)"
            }
        })

        # 4. Auto-resize columns
        requests.append({
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": 26
                }
            }
        })

    if requests:
        service.spreadsheet.batch_update({"requests": requests})
        print("\nSpreadsheet beautified successfully!")

if __name__ == "__main__":
    beautify()
