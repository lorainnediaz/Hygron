# IoT developer — Virtual IoT Workbench

Your interface is `simulation/app.py` (port 8502). Keep its simulator workflow readable and Wokwi-inspired rather than recreating actual Wokwi hardware emulation.

**Data flow:** BME680-like synthetic sensor values → virtual ESP32 (10 packets/5 min) → virtual Raspberry Pi validation/mean → simulated Internet bridge → SQLite `data/hygron_demo.sqlite3` → HCI dashboard on refresh → separate trained-model inference. Explain these on-hover or in a collapsed info panel. A network outage queues unsent summaries within the browser session; retry delivers after reconnect. A reset clears the pending queue, not the shared SQLite history.

**Room selection:** Choose Room 101–104 in the sidebar for a single-room staged walkthrough. Switching rooms clears only the unfinished staged packets; previously uploaded SQLite records are retained.

**Bulk demo:** 5 min, 1 h, 6 h, or 24 h × one or more selected rooms, with an environment scenario. It is demo-only, not physical sampling or real-time waiting. It requires the simulated Internet online. Default RH for rooms 101–104 is 64/73/84/91%. Do not silently generate historical data when the user expects a single staged click.

**Why not only Wokwi?** Wokwi is built for microcontroller/circuit simulation. Showing this full custom Python gateway, network buffering, SQLite storage and model-backed HCI interface in one demonstration requires surrounding services. No claim that Wokwi itself cannot interact with external services in other configurations.

Only change shared modules after coordination with the HCI developer; keep both apps pointing to the same local SQLite file. See `../README.md` for setup and limitations.

**Counters:** Raspberry Pi summaries counts summaries processed in this simulator session across both manual and bulk runs. Cloud records counts stored rows in shared SQLite (including dashboard-seeded history), so these totals need not match. Reset clears the session counter, not SQLite records.
