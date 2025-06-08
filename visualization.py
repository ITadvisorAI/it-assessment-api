import os
import pandas as pd
import matplotlib.pyplot as plt
import logging

logging.basicConfig(level=logging.INFO)

def generate_visual_charts(hw_data, sw_data, session_folder):
    charts = []

    os.makedirs(session_folder, exist_ok=True)

    # Chart 1: Hardware Tier Distribution
    if isinstance(hw_data, pd.DataFrame) and 'Tier' in hw_data.columns:
        chart_path = os.path.join(session_folder, "hw_tier_distribution.png")
        tier_counts = hw_data['Tier'].value_counts()
        tier_counts.plot(kind='bar', title='Hardware Tier Distribution')
        plt.xlabel("Tier")
        plt.ylabel("Count")
        plt.tight_layout()
        plt.savefig(chart_path)
        plt.close()
        logging.info(f"📊 Saved hardware chart: {chart_path}")
        charts.append(chart_path)

    # Chart 2: Software Tier Distribution
    if isinstance(sw_data, pd.DataFrame) and 'Tier' in sw_data.columns:
        chart_path = os.path.join(session_folder, "sw_tier_distribution.png")
        tier_counts = sw_data['Tier'].value_counts()
        tier_counts.plot(kind='bar', color='orange', title='Software Tier Distribution')
        plt.xlabel("Tier")
        plt.ylabel("Count")
        plt.tight_layout()
        plt.savefig(chart_path)
        plt.close()
        logging.info(f"📊 Saved software chart: {chart_path}")
        charts.append(chart_path)

    return charts
