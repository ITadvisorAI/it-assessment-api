
import os
import pandas as pd
import matplotlib.pyplot as plt

def generate_hw_charts(hw_gap_path, session_id):
    output_dir = os.path.join("temp_sessions", session_id)
    os.makedirs(output_dir, exist_ok=True)

    try:
        df = pd.read_excel(hw_gap_path, header=0)
        tier_counts = df['Tier'].value_counts()
        chart_path = os.path.join(output_dir, "hw_tier_distribution.png")
        tier_counts.plot.pie(autopct='%1.1f%%', startangle=90)
        plt.title("HW Tier Distribution")
        plt.ylabel('')
        plt.tight_layout()
        plt.savefig(chart_path)
        plt.close()
        return [chart_path]
    except Exception as e:
        print(f"❌ Failed to generate HW charts: {e}")
        return []

def generate_sw_charts(sw_gap_path, session_id):
    output_dir = os.path.join("temp_sessions", session_id)
    os.makedirs(output_dir, exist_ok=True)

    try:
        df = pd.read_excel(sw_gap_path, header=0)
        tier_counts = df['Tier'].value_counts()
        chart_path = os.path.join(output_dir, "sw_tier_distribution.png")
        tier_counts.plot.pie(autopct='%1.1f%%', startangle=90)
        plt.title("SW Tier Distribution")
        plt.ylabel('')
        plt.tight_layout()
        plt.savefig(chart_path)
        plt.close()
        return [chart_path]
    except Exception as e:
        print(f"❌ Failed to generate SW charts: {e}")
        return []
