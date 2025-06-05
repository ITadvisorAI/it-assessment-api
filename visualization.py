import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def ensure_chart_dir(session_id):
    chart_dir = f"temp_sessions/{session_id}/charts"
    os.makedirs(chart_dir, exist_ok=True)
    return chart_dir

def safe_plot_save(fig, path):
    fig.savefig(path, bbox_inches='tight')
    plt.close(fig)

def plot_tier_distribution(df, gap_type, session_id):
    chart_dir = ensure_chart_dir(session_id)
    if 'Tier' in df.columns and df['Tier'].notnull().any():
        counts = df['Tier'].value_counts()
        fig, ax = plt.subplots()
        ax.pie(counts.values, labels=counts.index, autopct='%1.1f%%')
        ax.set_title(f"{gap_type} Tier Distribution")
        path = os.path.join(chart_dir, f"{gap_type.lower()}_tier_distribution.png")
        safe_plot_save(fig, path)
        return path
    print(f"⚠️ No valid Tier data found for {gap_type}")
    return None

def plot_environment_distribution(df, gap_type, session_id):
    chart_dir = ensure_chart_dir(session_id)
    env_col = 'Environment' if 'Environment' in df.columns else 'Hosting Type'
    if env_col in df.columns and df[env_col].notnull().any():
        counts = df[env_col].value_counts()
        fig, ax = plt.subplots()
        sns.barplot(x=counts.index, y=counts.values, ax=ax)
        ax.set_title(f"{gap_type} Environment Distribution")
        ax.set_xlabel(env_col)
        ax.set_ylabel("Count")
        path = os.path.join(chart_dir, f"{gap_type.lower()}_environment_distribution.png")
        safe_plot_save(fig, path)
        return path
    print(f"⚠️ No valid environment data found for {gap_type}")
    return None

def plot_device_type_by_tier(df, session_id):
    chart_dir = ensure_chart_dir(session_id)
    if 'Hardware Type' in df.columns and 'Tier' in df.columns:
        pivot = df.pivot_table(index='Hardware Type', columns='Tier', aggfunc='size', fill_value=0)
        fig, ax = plt.subplots(figsize=(10, 6))
        pivot.plot(kind='bar', stacked=True, ax=ax)
        ax.set_title("Device Type vs Tier Distribution")
        path = os.path.join(chart_dir, "hw_device_type_vs_tier.png")
        safe_plot_save(fig, path)
        return path
    print("⚠️ 'Hardware Type' or 'Tier' column missing for HW device chart")
    return None

def generate_hw_charts(hw_path, session_id):
    try:
        df = pd.read_excel(hw_path, header=0)
        if df.empty:
            print(f"⚠️ No data in {hw_path}, skipping HW charts")
            return []
    except Exception as e:
        print(f"❌ Failed to read HW file: {e}")
        return []

    charts = []
    charts.append(plot_tier_distribution(df, "HW", session_id))
    charts.append(plot_environment_distribution(df, "HW", session_id))
    charts.append(plot_device_type_by_tier(df, session_id))
    return [c for c in charts if c]

def generate_sw_charts(sw_path, session_id):
    try:
        df = pd.read_excel(sw_path, header=0)
        if df.empty:
            print(f"⚠️ No data in {sw_path}, skipping SW charts")
            return []
    except Exception as e:
        print(f"❌ Failed to read SW file: {e}")
        return []

    charts = []
    charts.append(plot_tier_distribution(df, "SW", session_id))
    charts.append(plot_environment_distribution(df, "SW", session_id))
    return [c for c in charts if c]
