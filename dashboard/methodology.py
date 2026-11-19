"""Hygron methodology page."""
import streamlit as st


st.set_page_config(
    page_title="Hygron | Methodology",
    layout="wide",
)

st.title("Methodology")
st.caption("How the prototype works, from room conditions to staff decisions.")
st.markdown("""
**1. Collect room conditions.** A simulated BME680 sensor and ESP32 node generate temperature, relative humidity, and gas-resistance readings. These are examples, not physical measurements.

**2. Prepare the readings.** A simulated Raspberry Pi validates incoming packets and summarizes them into five-minute readings. A virtual network queue passes summaries to shared SQLite storage on the same computer. Network disconnections can delay delivery.

**3. Estimate risk.** Two trained Random Forest models classify the current condition and estimate one category **24 hours ahead**. They use engineered environmental features and were trained on simulated VTT-derived labels, not confirmed real-room mold observations.

**4. Support hotel decisions.** The dashboard organizes room risk, environmental trends and alerts so staff can prioritize inspection. An alert is a prompt to investigate conditions, not confirmation that mold is present.

**5. Understand limitations.** Forecasts are not hourly curves and are not proof of future mold. An evaluated direct 24-hour forecast had a macro-F1 of about 0.652 on held-out synthetic data; confidence intervals and calibrated probabilities are not available here.
""")
st.divider()
st.info("The Dashboard and IoT Workbench use the same local SQLite database. Readings generated in the workbench become visible on the dashboard after refreshing shared readings.")
