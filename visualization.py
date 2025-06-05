import os
import matplotlib.pyplot as plt
import pandas as pd

def generate_hw_charts(excel_path, session_id):
    try:
        df = pd.read_excel(excel_path, sheet_name=0)
        tier_counts = df['Tier'].value_counts()

        output_dir = os.path.join("temp_sessions", session_id)
        os.makedirs(output_dir, exist_ok=True)

        chart_path = os.path.join(output_dir, f"HW_Tier_Distribution_{session_id}.png")
        plt.figure(figsize=(6, 4))
        tier_counts.plot.pie(autopct='%1.1f%%', startangle=90, shadow=True)
        plt.title('Hardware Tier Distribution')
        plt.ylabel('')
        plt.tight_layout()
        plt.savefig(chart_path)
        plt.close()
        return chart_path

    except Exception as e:
        print(f"❌ Failed to generate HW charts: {e}")
        return None

def generate_sw_charts(excel_path, session_id):
    try:
        df = pd.read_excel(excel_path, sheet_name=0)
        tier_counts = df['Tier'].value_counts()

        output_dir = os.path.join("temp_sessions", session_id)
        os.makedirs(output_dir, exist_ok=True)

        chart_path = os.path.join(output_dir, f"SW_Tier_Distribution_{session_id}.png")
        plt.figure(figsize=(6, 4))
        tier_counts.plot.pie(autopct='%1.1f%%', startangle=90, shadow=True)
        plt.title('Software Tier Distribution')
        plt.ylabel('')
        plt.tight_layout()
        plt.savefig(chart_path)
        plt.close()
        return chart_path

    except Exception as e:
        print(f"❌ Failed to generate SW charts: {e}")
        return None
