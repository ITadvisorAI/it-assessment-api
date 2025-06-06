
import os
import pandas as pd
import matplotlib.pyplot as plt

def generate_charts(hw_df, sw_df, session_id):
    chart_dir = os.path.join("temp_sessions", session_id, "charts")
    os.makedirs(chart_dir, exist_ok=True)
    chart_paths = []

    def save_pie_chart(data, title, filename):
        try:
            plt.figure(figsize=(5, 5))
            data.plot.pie(autopct='%1.1f%%', startangle=90)
            plt.title(title)
            plt.ylabel('')
            path = os.path.join(chart_dir, filename)
            plt.tight_layout()
            plt.savefig(path)
            plt.close()
            chart_paths.append(path)
        except Exception as e:
            print(f"❌ Failed to generate chart {title}: {e}")

    if 'Tier' in hw_df.columns:
        save_pie_chart(hw_df['Tier'].value_counts(), "HW Tier Distribution", "hw_tier_distribution.png")
    if 'Status' in hw_df.columns:
        save_pie_chart(hw_df['Status'].value_counts(), "HW Status Breakdown", "hw_status_pie.png")

    if 'Tier' in sw_df.columns:
        save_pie_chart(sw_df['Tier'].value_counts(), "SW Tier Distribution", "sw_tier_distribution.png")
    if 'Status' in sw_df.columns:
        save_pie_chart(sw_df['Status'].value_counts(), "SW Status Breakdown", "sw_status_pie.png")

    return chart_paths
