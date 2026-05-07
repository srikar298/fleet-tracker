# System Architecture & Workflow

## Workflow Diagram

```mermaid
graph TD
    A[Driver Starts Bot] --> B{Registered?}
    B -- No --> C[KYC Registration Flow]
    C --> D[Save to Master_Drivers]
    B -- Yes --> E[Select Vehicle & Client]
    
    E --> F[Start Trip]
    F --> G[Upload Start ODO + Location]
    G --> H[Drive Phase]
    
    H --> I[End Trip]
    I --> J[Upload End ODO + Location]
    J --> K{Refuel?}
    K -- Yes --> L[Upload Fuel Receipt]
    K -- No --> M[Enter Trip Count]
    
    L --> M
    M --> N[Confirmation Summary]
    N --> O[Save to GSheets: Trips]
    O --> P[Update Dashboard KPIs]
    P --> Q[Check for Discrepancies/Flags]
```

## Data Architecture

### Google Sheets Schema
*   **Trips**: Transactional log of every duty. Includes `Trips_Count`, `Distance`, `Fuel_Cost`, and image links.
*   **Master_Vehicles**: Fleet registry with last known ODO and status (Idle/On Trip).
*   **Master_Drivers**: Driver KYC data (Phone, License, Name).
*   **Dashboard**: High-level KPI view using `COUNTIFS` and `SUMIFS` formulas.

### Security & Compliance
*   **KYC Storage**: All license photos are stored in a private Google Drive folder indexed by driver name.
*   **Fraud Detection**: The system flags trips where Odometer jumps are >300km or when start/end locations don't match the reported distance.
*   **Role-Based Access**: Drivers interact only via Telegram; managers have edit access to the Sheets backend.
