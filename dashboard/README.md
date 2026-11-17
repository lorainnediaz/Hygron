# HCI developer — Hotel Room Monitoring

Your interface is `dashboard/app.py` (port 8501). **Do not add an IoT simulation tab.** The Methodology page explains the pipeline in nontechnical language, ending with a link that opens the separate virtual IoT board in a new browser tab.

The IoT simulator is the writer; the dashboard is a **reader** of `shared_store.SQLiteCloud` backed by local `data/hygron_demo.sqlite3`. At first startup, the dashboard seeds each demo room with 60 days of synthetic history to support model inference. Refresh the dashboard after producing simulated readings; do not make the dashboard generate new five-minute readings on refresh.

### HCI scope

- Minimal overview with readable Low/Medium/High/Unavailable visual indicators, KPI summary cards, and risk-sorted room table. Use restrained color and non-color labels.
- Acknowledgable high-risk alerts with visible history. **Current alerts and acknowledgments are session-local**, not persistent across staff or restarts; do not describe them as real-time push notifications.
- Selected-room humidity time series with 80% RH reference line, 24h/7d/30d/60d filtering, tooltip detail and chart text alternative.
- Show **one** +24-hour risk category per selected room and a clear explanation of its limits; don't invent calibrated certainty or an hourly forecast.
- Evaluate with SUS, task success/time/errors; check contrast, semantic labels, keyboard use, readable sizing, non-color cues, and chart alternatives against relevant WCAG expectations.

The trained Random Forest estimates mold-conducive conditions, **not confirmed mold growth**. Separate device data from model output. See `../README.md` for shared setup, schema, and limitations.
