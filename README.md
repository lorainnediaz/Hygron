# Hygron — Virtual IoT Mold-Risk Monitoring Prototype

## React + FastAPI migration

The repository now includes an optional React HCI frontend backed by FastAPI:

```text
React (Vite)
  -> FastAPI REST API
  -> SQLite + existing ML bridge/inference

Existing Streamlit IoT Workbench
  -> Virtual sensor/ESP32/gateway/network pipeline
  -> Same SQLite database
```

The existing trained Random Forest models and IoT simulator remain unchanged. React does not reproduce feature engineering or model inference.

### React and FastAPI run commands

Terminal 1 — FastAPI:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Terminal 2 — React:

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:
- React: <http://127.0.0.1:5173>
- FastAPI docs: <http://127.0.0.1:8000/docs>

The existing unified Streamlit application remains available and can be run separately:

```powershell
python -m streamlit run app.py --server.port 8501
```

The React dashboard and Streamlit Workbench use the same `data/hygron_demo.sqlite3` database. Start the workbench in Streamlit to generate additional readings, then refresh the React dashboard.

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
- **Alerts:** React acknowledgments are persisted in local SQLite for the prototype. They are not multi-user notifications or confirmation that risk has been resolved.
- **Network/cloud:** No real ESP32 hardware, Raspberry Pi, Internet transport or hosted backend is used in this build.

## Tests

```powershell
python -m unittest test_integration.py -v
python -m unittest test_api.py -v
cd frontend
npm test
npm run lint
```

The integration tests cover representative data flow, SQLite handoff and network/bulk behaviors; they do not validate real sensor accuracy, actual network reliability, or deployment readiness.

## Dashboard completion checklist

- [x] React + Vite light-mode dashboard
- [x] FastAPI REST integration
- [x] Room risk table and room selection
- [x] Priority room warning panel
- [x] Latest-reading and system status
- [x] Selected-room staff guidance
- [x] Humidity history with 80% RH reference
- [x] Chart summary: latest RH, range, and percentage at/above 80%
- [x] Chart legend and text alternative
- [x] 24-hour outlook with direction
- [x] Forecast limitations and unavailable confidence label
- [x] Active and acknowledged alert states
- [x] SQLite-persisted alert acknowledgments
- [x] Responsive sidebar and dashboard layouts
- [x] Keyboard focus and reduced-motion styles
- [x] API tests for rooms, history, forecast, alerts, and unavailable data
- [x] Automated dashboard interaction tests
- [x] Mobile room-card layout
- [x] HCI task scenarios and heuristic evaluation template
- [x] HCI scenario-based usability testing guide
- [x] Risk-level explanations and plain-language reasons for Unavailable rooms
- [x] Alert acknowledgment retention policy (90 days by default, see below)
- [x] Participant testing kit (`docs/usability-testing-kit.md`)
- [ ] Complete mobile-device usability testing with participants
- [ ] Complete heuristic evaluation with participants
- [ ] Complete scenario-based usability testing with participants
- [ ] Calibrated forecast confidence (blocked, see below)
- [ ] Real hardware and hosted cloud integration

## Alert acknowledgment retention

Acknowledgments are stored in the `alert_acknowledgments` SQLite table. Each record holds only the alert ID and the time it was acknowledged. No staff names or guest information are stored.

- Records older than **90 days** are deleted each time the FastAPI backend starts.
- Change the period with `HYGRON_ALERT_ACK_RETENTION_DAYS` (whole days, at least 1). An invalid value stops the backend from starting, so a typo cannot silently disable cleanup.
- `/api/system-status` reports the active period as `alert_acknowledgment_retention_days`.
- An alert ID contains the room and reading time, so an alert older than the retention period shows as **Action needed** again if it is still the room's latest High reading. This is deliberate: an old acknowledgment should not hide a room that is still High.
- For a real deployment, confirm the period with the hotel's record-keeping policy before going live.

## Forecast confidence

The dashboard shows forecast confidence as unavailable and explains why. The Random Forest can output class scores, but those scores are not reliable probabilities until they are calibrated against labeled data the model has not seen. That labeled evaluation data is not included in this repository, so showing a percentage would overstate how sure the model is. To complete this item:

1. Get the held-out simulated evaluation set used for the macro-F1 figures above.
2. Calibrate the forecast model's scores on it (for example, scikit-learn `CalibratedClassifierCV`) and check the result with a reliability plot.
3. Only then show a confidence value, and keep the existing limitations text.

## HCI scenario-based usability test

Ask participants to complete these tasks without instructions beyond the task:

1. Identify the room that needs attention first and explain the reason.
2. Select another room and compare its humidity and temperature with the priority room.
3. Change the humidity-history range to 7 days.
4. Explain the 24-hour outlook and identify whether it predicts higher, lower, or unchanged risk.
5. Open and acknowledge a High-risk alert.
6. Explain what acknowledgment does and does not confirm.
7. Collapse and reopen the sidebar.
8. Repeat the main tasks using only a keyboard.

Record completion time, success/failure, errors, hesitation, confidence, and whether the participant interpreted risk as confirmed mold.

## HCI heuristic evaluation

Evaluate the dashboard with Nielsen's 10 heuristics:

| Heuristic | Review focus |
|---|---|
| Visibility of system status | Loading, refresh, acknowledgment, and data availability feedback |
| Match between system and real world | Room staff language and environmental terminology |
| User control and freedom | Sidebar, room selection, time range, and refresh |
| Consistency and standards | Risk colors, labels, buttons, and navigation |
| Error prevention | Unavailable data, acknowledgments, and invalid selections |
| Recognition rather than recall | Room table, legends, and selected-room state |
| Flexibility and efficiency | Fast room switching and responsive navigation |
| Aesthetic and minimalist design | Clear hierarchy without decorative clutter |
| Error diagnosis and recovery | Network, model, and missing-history messages |
| Help and documentation | Forecast limitations, chart alternative, and methodology |

For each finding record: screen, heuristic, severity from 0–4, evidence, and recommended fix.

## Accessibility checklist

- [x] Skip link to dashboard content
- [x] Visible keyboard focus
- [x] Sidebar open/close button labels
- [x] Room selection labels and pressed state
- [x] Chart legend and text alternative
- [x] Select menu keyboard support
- [x] Reduced-motion styles
- [x] Contrast pass for every risk and text state (WCAG AA, checked by `frontend/src/contrast.test.js`)
- [x] Automated keyboard-only test for every primary task (`frontend/src/App.keyboard.test.jsx`)
- [x] Automated axe-core semantics check (`frontend/src/App.a11y.test.jsx`)
- [ ] Screen-reader pass with a complete workflow (needs a person using NVDA or VoiceOver; script in the testing kit)
- [ ] Keyboard-only test with participants

## Reset local demo data

Stop **both** apps before deleting `data/hygron_demo.sqlite3` and any `-wal` / `-shm` sidecar files. Restart the dashboard to regenerate synthetic starter history. **This deletes local simulation data**, so back it up if you need it.

## GitHub and collaboration

Generated database files, caches and virtual environments are excluded by `.gitignore`. The provided model artifacts are included in this prototype because the dashboard uses them; each file is below GitHub's 100 MiB single-file limit. Do not commit passwords, real guest information or private configuration files.

If the GitHub repository already exists, see the push instructions supplied alongside this README. For team collaboration, use separate branches for `dashboard/` (HCI) and `simulation/` (IoT), and review changes to shared modules together.

## Academic scope

Hygron demonstrates the integration of **IoT (COSC 111)**, **HCI (ITEC 80)** and **supervised ML (COSC 105)** through a software prototype. It is for teaching, demonstration and evaluation—not building certification, physical mold detection or production hotel monitoring.


---

# Development Handover Guide

Hygron is an existing Software-in-the-Loop (SIL) Digital Twin prototype integrating virtual IoT devices, machine learning, and a client-facing monitoring dashboard.

| Developer | Assignment | Primary Responsibility |
|---|---|---|
| Paolo | IoT | Improve the virtual hardware simulation, component visualization, and data-flow demonstration |
| Karlo and Han | HCI | Improve the client-facing dashboard, usability, accessibility, and presentation of monitoring information |

Developers are encouraged to explore their own design ideas. The existing implementation serves as the foundation, not a strict limitation on visual design or interaction.

## Paolo — IoT Simulation

### Objective

Improve the existing IoT Workbench to resemble an interactive, Wokwi-inspired hardware simulation.

The simulator should clearly communicate how environmental data travels through the following architecture:

**BME680 Sensor → ESP32 → Raspberry Pi Edge Gateway → Internet → Cloud → Machine Learning → Streamlit Dashboard**

Users should be able to understand the purpose of each simulated component and observe how information moves through the system when the simulation runs.

### Suggested Improvements

- Improve the appearance and arrangement of virtual components.
- Make components resemble physical hardware or recognizable electronic modules.
- Represent wired and wireless connections appropriately.
- Improve packet or particle animations during data transmission.
- Make the simulation stages more understandable through visual feedback.
- Add an information tooltip or explanation when a simulation stage is triggered.
- Improve the overall interaction and presentation of the IoT Workbench.

These are suggestions, not strict implementation requirements. The developer may introduce alternative designs as long as the underlying architecture remains understandable and functional.

### Why We Are Not Using Wokwi Exclusively

Wokwi is useful for demonstrating virtual circuits, microcontrollers, sensors, and embedded programming.

However, Hygron's machine learning models were trained in Python using scikit-learn and require historical environmental features extending up to 60 days.

Running the existing ML pipeline directly inside a Wokwi ESP32 would require additional work, including translating or replacing the Python inference logic and implementing historical feature processing in an embedded environment.

Our system also simulates Raspberry Pi edge processing, Internet connectivity, cloud storage, and a separate client dashboard.

For these reasons, we selected a Python-based SIL Digital Twin that represents the complete architecture without requiring firmware conversion.

A separate Wokwi demonstration may still be used as supplementary evidence of the proposed hardware design.

### Relevant IoT Files

| File | Purpose |
|---|---|
| `simulation/app.py` | Main IoT Workbench interface and simulation controls |
| `board_visual.py` | Virtual hardware board and data-flow visualization |
| `sensor_simulator.py` | Virtual environmental sensor and ESP32 behavior |
| `edge_gateway.py` | Raspberry Pi edge processing, validation, and aggregation |
| `network_cloud.py` | Simulated Internet connectivity and cloud transmission |
| `simulation/bulk_engine.py` | Multi-room simulation and time advancement |
| `shared_store.py` | Shared SQLite data storage |
| `simulation/README.md` | Additional simulator documentation |

### Important Warnings

1. **Do not break the existing simulation pipeline.** Changes to animations or component visuals should not interfere with data generation, validation, aggregation, or storage.

2. **Visual data transmission should represent actual simulation stages.** Avoid showing successful delivery when the ESP32 or Internet connection is offline.

3. **Keep simulated components clearly identified.** The Raspberry Pi, Internet, sensors, and cloud are represented through Python rather than physical hardware or external cloud services.

4. **Preserve room-specific simulation data.** Switching or simulating multiple rooms should not overwrite another room's history or introduce unintended timestamp gaps.

5. **Coordinate changes to shared files.** Changes to `shared_store.py`, `ml_bridge.py`, or data structures may affect the HCI dashboard.

---

## Han and Karlo — HCI Dashboard

### Objective

Improve Hygron's client-facing dashboard for hotel owners, facility managers, and maintenance personnel.

The goal is to make environmental monitoring and mold-growth risk information easy to understand, accessible, and useful for decision-making.

The developer has creative freedom regarding layout, navigation, visual style, components, and interactions.

### HCI Areas to Consider

The dashboard should continue supporting the project's main HCI focus areas:

- **Real-time risk status and visual indicators**
- **Alerts and notification design**
- **Trend visualization and historical views**
- **Forecasting and predictive decision support**
- **Usability evaluation**
- **Accessibility and inclusive design**

The developer may improve existing components, reorganize information, or introduce additional features where appropriate.

Design decisions should consider clarity, information overload, alert fatigue, accessible status indicators, and the needs of non-technical hotel personnel.

For evaluation, consider the System Usability Scale (SUS), task success rate, completion time, and user errors.

Accessibility improvements should consider WCAG-aligned practices such as sufficient contrast, readable typography, semantic structure, non-color indicators, and text alternatives for important charts.

### Relevant HCI Files

| File | Purpose |
|---|---|
| `dashboard/app.py` | Main client-facing HCI dashboard |
| `app.py` | Root Streamlit application entry point |
| `ml_bridge.py` | Connects historical room data to ML inference |
| `inference.py` | Loads trained ML models and produces risk estimates |
| `shared_store.py` | Reads and stores room monitoring data |
| `models/current_risk_rf.joblib` | Trained current-risk Random Forest |
| `models/forecast_24h_rf.joblib` | Trained 24-hour forecasting Random Forest |
| `models/model_metadata.json` | Model features, labels, and configuration |
| `dashboard/README.md` | Additional dashboard documentation |

### Important Warnings

1. **Do not replace actual ML predictions with hardcoded risk labels.** Low, Medium, and High statuses should reflect the model output whenever valid predictions are available.

2. **Do not present simulated readings as real-world sensor measurements.** This is a software-based prototype.

3. **Do not present forecasting as guaranteed.** The 24-hour forecast is supplementary and has documented limitations, particularly in anticipating changes in risk.

4. **Do not imply that Hygron detects physical mold.** The models estimate VTT-derived mold-growth risk based on environmental conditions.

5. **Do not rely on color alone.** Risk statuses should also use text, icons, or other understandable indicators.

6. **Avoid excessive alerts.** Notifications should help staff identify important conditions without overwhelming users.

7. **Handle unavailable predictions clearly.** Offline sensors, incomplete history, and model errors should not be displayed as Low risk.

8. **Preserve ML compatibility.** The models depend on nine specific features and historical environmental data. Changes to feature generation or model inputs must be coordinated before implementation.

9. **Coordinate changes to shared modules.** The dashboard and IoT Workbench use the same underlying monitoring data.

---

## Shared Task — Timezone Consistency

**Both developers must address timezone consistency.**

Hygron is intended for use in the Philippines. The application's default display timezone should therefore be:

`Asia/Manila (UTC+08:00)`

Review timestamp handling throughout the IoT simulator, shared database, machine learning pipeline, and HCI dashboard.

### Important Considerations

- Store timestamps using a consistent timezone convention, preferably UTC.
- Convert timestamps to `Asia/Manila` when presenting them to users.
- Clearly distinguish simulated time from actual system time.
- Avoid mixing timezone-aware and timezone-naive timestamps.
- Preserve chronological ordering when calculating historical ML features.
- Ensure that simulation, alert, and forecast timestamps refer to the correct time.
- Avoid changing the interpretation of existing historical records without checking compatibility.

The 24-hour forecast should be displayed relative to the latest simulated observation, not automatically relative to the user's actual current clock.

---

## General Development Guidelines

- Preserve the existing working implementation before making major changes.
- Use separate Git branches for IoT and HCI development.
- Avoid unnecessarily modifying trained models or established ML feature definitions.
- Test the application after changes.
- Keep documentation updated when adding or changing functionality.
- Communicate before editing shared modules.
- Do not commit temporary databases, caches, environment files, or credentials.
- Keep experimental functionality clearly distinguished from completed functionality.

### Suggested Git Branches

- `feature/iot-improvements`
- `feature/hci-improvements`

Both developers should work independently on their respective branches and merge tested changes into `main`.

### Existing Prototype Scope

Hygron currently demonstrates a software-simulated IoT architecture with a virtual Raspberry Pi gateway, Internet connection, cloud storage, machine learning inference, and client dashboard.

The objective of this handover is to improve the quality, usability, and presentation of the existing system while maintaining its core functionality.

---

