# Hygron — Virtual IoT Mold-Risk Monitoring Prototype

**Hygron** is a software-in-the-loop (SIL) prototype for monitoring environmental conditions in simulated hotel guest rooms. It combines a virtual IoT sensor-to-cloud pipeline, trained machine learning models for **current mold-growth risk** and a **24-hour risk category forecast**, and a hotel-staff-facing dashboard.

> **Prototype disclaimer:** All sensor data, ESP32/Raspberry Pi devices, network connections and cloud behavior are **simulated**. The cloud is represented by a **local SQLite database**, not a hosted cloud service. The models estimate conditions associated with mold growth; they **do not detect or confirm mold**. The models were trained on synthetic data with VTT-derived risk labels.

## Features

### Hotel dashboard (HCI)
- **Room overview:** Rooms 101–104, Low / Medium / High / Unavailable indicators, KPI cards and risk-prioritized table.
- **Alerts:** Current High-risk notifications, acknowledgment controls and session-local alert history.
- **Historical trends:** Per-room humidity and temperature charts, an 80% RH reference line and selectable time ranges.
- **Predictive support:** One predicted risk class **24 hours ahead**. This is not an hourly forecast curve or a reliable early-transition alert.
- **Methodology:** A small link opens the separate Virtual IoT Workbench for transparency.

### Virtual IoT Workbench
- Virtual **BME680-like sensor** and **ESP32** generate ten 30-second samples per five-minute cycle.
- Virtual **Raspberry Pi edge gateway** validates data and aggregates five-minute summaries.
- Simulated **Internet connection** queues uploads while offline and forwards them after reconnection.
- Virtual **cloud** persists delivered summaries in local SQLite.
- Wokwi-inspired component visualization, stage-by-stage walkthrough, room selection and accelerated bulk scenarios.

## Architecture

```text
Simulated room conditions
        |
Virtual BME680 sensor -> Virtual ESP32 (30-second packets)
        |
Virtual Raspberry Pi edge gateway (validation + 5-minute summaries)
        |
Simulated Internet (online/offline, in-session upload queue)
        |
Virtual cloud (local SQLite: data/hygron_demo.sqlite3)
        |
60-day historical feature builder (nine inputs)
        |
Saved Random Forest models
        |-- Current Low / Medium / High risk
        `-- Single risk category at +24 hours
        |
Client Streamlit dashboard (manual refresh)
```

The **dashboard and workbench are separate Streamlit processes** reading/writing the same database on the **same machine**. The workbench produces new readings; the dashboard reads delivered summaries and performs inference. The methodology board does not run the Random Forest inside an ESP32.

## Technology

Python, Streamlit, pandas, NumPy, Altair, scikit-learn, joblib and SQLite. The delivered `.joblib` models were trained using **scikit-learn 1.7.2** (see `models/model_metadata.json`). Use model artifacts only from trusted sources.

## Project layout

```text
hygron_client_dashboard/
├── dashboard/
│   ├── app.py                 # Hotel-facing dashboard (port 8501)
│   └── README.md
├── simulation/
│   ├── app.py                 # Virtual IoT workbench (port 8502)
│   ├── bulk_engine.py
│   └── README.md
├── models/
│   ├── current_risk_rf.joblib
│   ├── forecast_24h_rf.joblib
│   └── model_metadata.json
├── data/                      # Generated SQLite data; not committed
├── sensor_simulator.py
├── edge_gateway.py
├── network_cloud.py
├── shared_store.py
├── ml_bridge.py
├── inference.py
├── board_visual.py
├── test_integration.py
├── requirements.txt
├── app.py                     # Compatibility launcher for dashboard
└── README.md
```

## Run locally (Windows PowerShell)

**Prerequisites:** Python, pip, and a terminal. Run commands in the folder containing `requirements.txt`.

```powershell
# Optional but recommended: isolate dependencies
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install -r requirements.txt

# The included models were trained with scikit-learn 1.7.2
python -m pip install "scikit-learn==1.7.2"
```

If PowerShell blocks activation, skip activation and use `py -m pip ...` and `py -m streamlit ...` with your chosen Python environment, or use `.\.venv\Scripts\python.exe -m ...`.

**Terminal 1 — Hotel dashboard:**

```powershell
python -m streamlit run dashboard/app.py --server.port 8501
```

**Terminal 2 — Virtual IoT Workbench** (same folder, same Python environment):

```powershell
python -m streamlit run simulation/app.py --server.port 8502
```

Open:
- Dashboard: <http://localhost:8501>
- IoT workbench: <http://localhost:8502>

Start the **dashboard first** to seed four demo rooms with 60 days of synthetic history. In the workbench, choose a room and scenario, advance the staged simulation or generate bulk demonstration readings. Return to the dashboard and click **Refresh shared readings** to view delivered summaries.

Both apps must see the same SQLite file. If needed, set the identical absolute `HYGRON_DB_PATH` environment variable in both terminals. Set `HYGRON_SIMULATION_URL` to the workbench's accessible address if it is not `http://localhost:8502`.

## Demo walkthrough

1. Open the dashboard: inspect the room table, KPI cards, risk status, trends and forecast.
2. Follow the small **Methodology / Virtual IoT Workbench** link.
3. Choose Room 101–104 and a scenario (normal, humidity spike, prolonged dampness or condensation-like conditions).
4. Advance one five-minute cycle to show virtual sensor → ESP32 → Raspberry Pi → Internet → cloud. Or use accelerated bulk simulation for selected rooms.
5. Turn the simulated Internet offline to observe the upload queue, then reconnect and deliver queued summaries.
6. Refresh the dashboard to display newly delivered readings and updated model outputs.

**Simulation notes:** Changes in room risk may be gradual because the ML model uses 60-day history. Some missing or discontinuous five-minute readings can make inference show **Unavailable** until sufficient continuous history is present. Bulk generation advances simulated time, not wall-clock time. The network queue is session-local and can be lost on reset; SQLite records persist between app sessions.

## ML details and limitations

- **Current status:** Random Forest three-class classification (Low, Medium, High), color and text indicators.
- **24-hour outlook:** Separate Random Forest predicting the category **exactly +24 hours**, not every hour in between.
- **Nine features:** RH, temperature, dew point, dew-point margin, 24-hour mean RH, 60-day mean RH, 24-hour RH standard deviation, one-hour RH change and fraction of readings at/above 80% RH over 60 days.
- **Training:** Simulated VTT-derived mold-growth categories, not real hotel mold inspections.
- **Evaluation on an independent simulated 12-room batch:** Current-risk macro-F1 approximately **0.692**; 24-hour forecast macro-F1 approximately **0.652**. The forecast struggled to anticipate risk transitions and should not be treated as a dependable early warning.
- **History requirement:** The UI seeds 60 days of synthetic readings for demonstration. No calibrated forecast confidence is provided.
- **Alerts:** Acknowledgments/history are **local to the active Streamlit dashboard session**, not persistent multiuser notifications.
- **Network/cloud:** No real ESP32 hardware, Raspberry Pi, Internet transport or hosted backend is used in this build.

## Tests

```powershell
python -m unittest test_integration.py -v
```

The integration tests cover representative data flow, SQLite handoff and network/bulk behaviors; they do not validate real sensor accuracy, actual network reliability, or deployment readiness.

## Reset local demo data

Stop **both** apps before deleting `data/hygron_demo.sqlite3` and any `-wal` / `-shm` sidecar files. Restart the dashboard to regenerate synthetic starter history. **This deletes local simulation data**, so back it up if you need it.

## GitHub and collaboration

Generated database files, caches and virtual environments are excluded by `.gitignore`. The provided model artifacts are included in this prototype because the dashboard uses them; each file is below GitHub's 100 MiB single-file limit. Do not commit passwords, real guest information or private configuration files.

If the GitHub repository already exists, see the push instructions supplied alongside this README. For team collaboration, use separate branches for `dashboard/` (HCI) and `simulation/` (IoT), and review changes to shared modules together.

## Academic scope

Hygron demonstrates the integration of **IoT (COSC 111)**, **HCI (ITEC 80)** and **supervised ML (COSC 105)** through a software prototype. It is for teaching, demonstration and evaluation—not building certification, physical mold detection or production hotel monitoring.
