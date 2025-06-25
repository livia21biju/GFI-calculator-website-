from flask import Flask, render_template, request
import pandas as pd
import numpy as np
import json

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def fuel_form():
    fuel_types = [
        "Heavy Fuel Oil (HFO)",
        "Marine Gas Oil (MGO)",
        "Liquefied Natural Gas (LNG)",
        "Bio-24",
        "e-ammonia",
        "bio-methanol"
    ]

    results_table = None
    ghg = 0
    total_fuel = 0
    total_penalty=0 
    fuel_data = []
    custom_fuel_data = []
    chart_data = {}

    if request.method == "POST":
        # Standard fuel inputs
        lhv_list = request.form.getlist("lhv")
        ghg_list = request.form.getlist("ghg")
        quantity_list = request.form.getlist("consumed")
        price_list = request.form.getlist("price")

        # Custom fuel inputs
        custom_type_list = request.form.getlist("custom_type")
        custom_lhv_list = request.form.getlist("custom_lhv")
        custom_ghg_list = request.form.getlist("custom_ghg")
        custom_qty_list = request.form.getlist("custom_consumed")
        custom_price_list = request.form.getlist("custom_price")

        # Pricing inputs
        surplus_costrate = float(request.form.get("surplus_price", 240))
        Tier_1_cost = float(request.form.get("tier1_price", 100))
        Tier_2_cost = float(request.form.get("tier2_price", 380))

        fuels = []

        # Standard fuels
        for i in range(len(fuel_types)):
            try:
                lhv = float(lhv_list[i])
                ghg = float(ghg_list[i])
                qty = float(quantity_list[i])
                price = float(price_list[i])
                if qty > 0 and lhv > 0 and ghg > 0:
                    fuels.append({"lcv": lhv, "ghg": ghg, "quantity": qty})
                fuel_data.append({
                    "type": fuel_types[i],
                    "lhv": lhv,
                    "ghg": ghg,
                    "consumed": qty,
                    "price": price
                })
            except:
                fuel_data.append({
                    "type": fuel_types[i],
                    "lhv": "",
                    "ghg": "",
                    "consumed": "",
                    "price": ""
                })

        # Custom fuels
        for i in range(len(custom_type_list)):
            try:
                lhv = float(custom_lhv_list[i])
                ghg = float(custom_ghg_list[i])
                qty = float(custom_qty_list[i])
                price = float(custom_price_list[i])
                if qty > 0 and lhv > 0 and ghg > 0:
                    fuels.append({"lcv": lhv, "ghg": ghg, "quantity": qty})
                custom_fuel_data.append({
                    "type": custom_type_list[i],
                    "lhv": lhv,
                    "ghg": ghg,
                    "consumed": qty,
                    "price": price
                })
            except:
                continue

        # GFI calculation
        total_energy = sum(f["lcv"] * f["quantity"] for f in fuels)
        total_ghg_emission = sum(f["lcv"] * f["ghg"] * f["quantity"] for f in fuels)
        weighted_ghg = round(total_ghg_emission / total_energy, 2) if total_energy else 0
        total_fuel = round(sum(f["quantity"] for f in fuels), 2)
        


        df = pd.DataFrame({
            'Year': [2028, 2029, 2030, 2031, 2032, 2033, 2034, 2035],
            'GHG BT': [89.568, 87.702, 85.836, 81.7308, 77.6256, 73.5204, 69.4152, 65.31],
            'GHG DT': [77.439, 75.573, 73.707, 69.6018, 65.4966, 61.3914, 57.2862, 53.181]
        })

        df['Tier'] = np.select(
            [weighted_ghg > df['GHG BT'],
             (weighted_ghg >= df['GHG DT']) & (weighted_ghg <= df['GHG BT'])],
            [2, 1], default=0
        )

        df['Attained GFI'] = weighted_ghg

        df['Compliance Tier 2'] = np.where(df['Tier'] == 2,
                                           (df['GHG BT'] - weighted_ghg) * total_energy, 0)
        df['Compliance Tier 1'] = np.where(df['Tier'] == 2,
                                           (df['GHG DT'] - df['GHG BT']) * total_energy,
                                           np.where(df['Tier'] == 1,
                                                    (df['GHG DT'] - weighted_ghg) * total_energy, 0))

        df['Compliance Tier 1 cost'] = -(df['Compliance Tier 1'] * Tier_1_cost)
        df['Compliance Tier 2 cost'] = -(df['Compliance Tier 2'] * Tier_2_cost)
        df['Total_Penalty'] = df['Compliance Tier 1 cost'] + df['Compliance Tier 2 cost']

        df['Surplus Cost'] = np.where(
            df['Tier'] == 0,
            (weighted_ghg - df['GHG DT']) * total_energy * -surplus_costrate,
            0
        )

        # ✅ Fix: Replace NaN with 0 to prevent JS chart issues
       # Replace NaN with 0
        df.fillna(0, inplace=True)

        # Calculate chart data BEFORE formatting columns with "$"
        raw_total_penalty = round(df["Total_Penalty"].sum(), 2)
        surplus_ru = df["Surplus Cost"].round(2).tolist()

        chart_data = {
          "years": df['Year'].tolist(),
          "attained": df['Attained GFI'].tolist(),
          "ghg_bt": df['GHG BT'].tolist(),
          "ghg_dt": df['GHG DT'].tolist(),
          "tier1_ru": df['Compliance Tier 1'].round(2).tolist(),
          "tier2_ru": df['Compliance Tier 2'].round(2).tolist(),
          "surplus_ru": surplus_ru
}

        # Rename columns to include dollar symbol in header only
        df.rename(columns={
        "Compliance Tier 1 cost": "Compliance Tier 1 cost ($)",
        "Compliance Tier 2 cost": "Compliance Tier 2 cost ($)",
        "Surplus Cost": "Surplus Cost ($)"
         }, inplace=True)

         # Recalculate total_penalty if needed (already done above with raw numeric)
        total_penalty = raw_total_penalty

         # Swap Tier 1 and Tier 2 columns for display
        cols = list(df.columns)
        if "Compliance Tier 1" in cols and "Compliance Tier 2" in cols:
          i1 = cols.index("Compliance Tier 1")
          i2 = cols.index("Compliance Tier 2")
        cols[i1], cols[i2] = cols[i2], cols[i1]
        df = df[cols]

        # Generate HTML table
        results_table = df.round(2).to_html(classes="styled-table", index=False)

    else:
        fuel_data = [{"type": ft, "lhv": "", "ghg": "", "consumed": "", "price": ""} for ft in fuel_types]
        custom_fuel_data = []

    return render_template(
        "ref_calculator.html",
        fuel_data=fuel_data,
        custom_fuel_data=custom_fuel_data,
        results_table=results_table,
        ghg=ghg, 
        total_fuel=total_fuel,
        total_penalty=total_penalty,
        chart_data=json.dumps(chart_data)

    )

if __name__ == '__main__':
    app.run(debug=True)
