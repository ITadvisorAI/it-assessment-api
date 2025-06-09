import os
import matplotlib.pyplot as plt

def generate_charts(hw_df, sw_df, session_folder):
    os.makedirs(os.path.join(session_folder, "charts"), exist_ok=True)

    def pie_chart(data, column, title, filename):
        counts = data[column].value_counts()
        plt.figure(figsize=(5, 5))
        plt.pie(counts, labels=counts.index, autopct='%1.1f%%', startangle=140)
        plt.title(title)
        chart_path = os.path.join(session_folder, "charts", filename)
        plt.savefig(chart_path)
        plt.close()
        return chart_path

    charts = {}

    if hw_df is not None and not hw_df.empty:
        if "Tier" in hw_df:
            charts["hw_tier_chart"] = pie_chart(hw_df, "Tier", "Hardware Tier Distribution", "hw_tier_chart.png")
        if "Status" in hw_df:
            charts["hw_status_chart"] = pie_chart(hw_df, "Status", "Hardware Status", "hw_status_chart.png")

    if sw_df is not None and not sw_df.empty:
        if "Tier" in sw_df:
            charts["sw_tier_chart"] = pie_chart(sw_df, "Tier", "Software Tier Distribution", "sw_tier_chart.png")
        if "Status" in sw_df:
            charts["sw_status_chart"] = pie_chart(sw_df, "Status", "Software Status", "sw_status_chart.png")

    return charts

# Patch to match expected import name
generate_visual_charts = generate_charts
