# Dashboard Screenshots

This folder is designated for capturing and storing visual previews of the **Cryptocurrency Price Tracker** application. Adding clear screenshots greatly enhances your GitHub portfolio repository by providing recruiters, interviewers, and collaborators with an immediate visual demonstration of your project.

---

## Recommended Screenshots to Add

1. **`dashboard_overview.png`**
   - **What to capture:** The main dashboard view featuring the top KPI metric cards (Bitcoin, Ethereum, Top Gainer/Loser), currency switcher (USD / INR), and the interactive market summary table.
   - **Tip:** Ensure the sidebar is expanded so viewers can see available filters and the CoinGecko attribution badge.

2. **`interactive_charts.png`**
   - **What to capture:** The **Market Comparisons** tab displaying the horizontal bar chart for Market Capitalization and the 24-hour Percentage Change comparison chart.
   - **Tip:** Hover your cursor over one of the bars to demonstrate the interactive Plotly tooltip showing exact values and formatting.

3. **`historical_trends.png`**
   - **What to capture:** The **Historical Price Trends** tab showing the interactive price line chart across 1-day, 7-day, or 30-day intervals.
   - **Tip:** Show the zoom and pan toolbar or a custom timeframe selected (e.g., 30 Days for Bitcoin or Solana).

4. **`search_and_export.png`**
   - **What to capture:** The filtered view after typing a query in the search bar (e.g., searching for "Solana" or "Cardano") along with the CSV download button.

---

## How to Capture and Save Screenshots

### On Windows 10 / 11:
1. Run the Streamlit app locally:
   ```powershell
   streamlit run app.py
   ```
2. Open your browser at `http://localhost:8501`.
3. Press <kbd>Windows Key</kbd> + <kbd>Shift</kbd> + <kbd>S</kbd> to launch the Snipping Tool.
4. Select the dashboard area to capture.
5. Save the captured image directly into this `screenshots/` directory using the recommended filenames above.

---

## Referencing Screenshots in `README.md`

Once you place the images in this directory, link them in the root `README.md` using standard Markdown syntax:

```markdown
![CryptoPulse Dashboard Overview](screenshots/dashboard_overview.png)
![Interactive Charts](screenshots/interactive_charts.png)
```
