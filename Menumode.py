import datetime
import pandas as pd
import os

import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

# ---------------- DEFAULT VALUES ----------------
current_date_obj = datetime.datetime.now()
current_bill_date = current_date_obj.strftime("%d-%m-%Y")
bill_month = current_date_obj.strftime("%B")
last_slope_line = None

# ---------------- FILE STORAGE ----------------
base_folder = r"C:\Users\Shreyas Karangutkar\Desktop\EBS Backup\Profiles"
file_path = os.path.join(base_folder, "EBSfull.xlsx")  # default

# Electricity part
fixed_charge = 140.00
tr_multiplier = 1.47
fac = 13.40
raw_tax_percent = 16.0
est = 0.0

# Account part
base_other_charges = 0.00
interest = 0.00
net_arrears = 0.00
adjusted_amount = 0.00
interest_arrears = 0.00

# penalty per day
penalty_per_day = 10.00

# ---------------- CREATE OR READ PROFILE TXT ----------------
def create_or_read_profile_txt(person_name, force_edit=False):

    clean_name = "".join(person_name.split())
    txt_file = os.path.join(base_folder, f"Profile_{clean_name}.txt")

    profile_data = {}

    # ---------- READ EXISTING PROFILE ----------
    if os.path.exists(txt_file) and not force_edit:
        try:
            with open(txt_file, "r") as f:
                for line in f:
                    if ":" in line:
                        key, value = line.strip().split(":", 1)
                        profile_data[key.strip()] = value.strip()

            # ---------- PASSWORD CHECK ----------
            stored_password = profile_data.get("Password", "")

            attempts = 0
            while attempts < 3:
                entered_password = input("Enter Password ('r' to retry): ").strip()

                if entered_password.lower() == "r":
                    continue

                if entered_password == stored_password:
                    print(f"✅ Access Granted. Welcome {person_name}")
                    return profile_data
                else:
                    attempts += 1
                    print(f"❌ Wrong Password! Attempts left: {3-attempts}")

            print("❌ Too many wrong attempts. Returning to name selection.")
            return {}

        except Exception as e:
            print("[ERROR reading profile txt]", e)
            return {}

    # ---------- CREATE NEW PROFILE ----------
    print(f"\n📝 Creating new profile for {person_name}...")

    # ---------- PASSWORD ----------
    while True:
        password = input("Create Password (min 4 chars) ('r' to retry): ").strip()

        if password.lower() == "r":
            continue

        if len(password) < 4:
            print("⚠️ Password must be at least 4 characters.")
            continue

        confirm = input("Confirm Password: ").strip()

        if password != confirm:
            print("⚠️ Passwords do not match.")
            continue

        profile_data["Password"] = password
        break

    # ---------- ADDRESS ----------
    while True:
        address = input("Enter Address (RoomNumber Wing Building Sector City) ('r' to retry): ").strip()
        if address.lower() == "r":
            continue
        if len(address.split()) < 5:
            print("⚠️ Address must contain RoomNumber, Wing, Building, Sector, City.")
            continue
        profile_data["Address"] = address
        break

    # ---------- GENDER ----------
    while True:
        gender = input("Enter Gender (Male/Female or M/F) ('r' to retry): ").strip().lower()
        if gender == "r":
            continue
        if gender in ["male", "m"]:
            profile_data["Gender"] = "Male"
            break
        elif gender in ["female", "f"]:
            profile_data["Gender"] = "Female"
            break
        else:
            print("⚠️ Invalid input! Enter Male/Female or M/F.")

    # ---------- AGE ----------
    while True:
        age = input("Enter Age (10-99) ('r' to retry): ").strip()
        if age.lower() == "r":
            continue
        if age.isdigit() and 10 <= int(age) <= 99:
            profile_data["Age"] = age
            break
        print("⚠️ Age must be 10-99.")

    # ---------- FAMILY ----------
    while True:
        family = input("Enter Number of Family Members (0-9) ('r' to retry): ").strip()
        if family.lower() == "r":
            continue
        if family.isdigit() and 0 <= int(family) <= 9:
            profile_data["Family Members"] = family
            break
        print("⚠️ Family Members must be 0-9.")

    # ---------- SAVE FILE ----------
    try:
        with open(txt_file, "w") as f:
            f.write(f"Name: {person_name}\n")
            f.write(f"Password: {profile_data['Password']}\n")

            for key in ["Address", "Gender", "Age", "Family Members"]:
                f.write(f"{key}: {profile_data[key]}\n")

        print(f"✅ Profile saved: {txt_file}")

    except Exception as e:
        print("[ERROR saving profile txt]", e)

    return profile_data

# ---------------- GET LAST REMAIN AMOUNT ----------------
def get_previous_remain_amount(current_bill_date):

    if not os.path.exists(file_path):
        return 0.0

    try:

        df = pd.read_excel(file_path)

        df.columns = df.columns.str.strip()

        if df.empty:
            return 0.0

        if "Date" not in df.columns or "Remaining" not in df.columns:
            return 0.0

        df["Date"] = pd.to_datetime(df["Date"], format="%d-%m-%Y", errors="coerce")

        current_date = datetime.datetime.strptime(current_bill_date, "%d-%m-%Y")

        # get all rows BEFORE current bill date
        previous_rows = df[df["Date"] < current_date]

        if previous_rows.empty:
            return 0.0

        previous_rows = previous_rows.sort_values("Date")

        last_remain = previous_rows.iloc[-1]["Remaining"]

        if pd.isna(last_remain):
            return 0.0

        return float(last_remain)

    except Exception as e:
        print("[ERROR reading previous remain]", e)
        return 0.0

# ---------------- SPIKE PENALTY / REWARD ----------------
def calculate_spike_adjustment(current_units, current_bill_date):

    previous_units = get_previous_units(current_bill_date)

    # No previous data → no adjustment
    if previous_units == 0:
        return 0.0, 0.0, previous_units

    change = current_units - previous_units

    spike_percent = (change / previous_units) * 100

    adjustment = 0.0

    # -------- SPIKE UP (Penalty) --------
    if spike_percent >= 30:

        extra_units = change

        # Rs. 2 penalty per extra unit
        adjustment = extra_units * 2.0

    # -------- SPIKE DOWN (Reward) --------
    elif spike_percent <= -20:

        saved_units = abs(change)

        # Rs. 1 reward per saved unit
        adjustment = -saved_units * 1.0

        # Cap max reward
        adjustment = max(adjustment, -500)

    return adjustment, spike_percent, previous_units
# ---------------- CALCULATE PENALTY ----------------
def calculate_penalty():

    global current_bill_date

    try:

        date_obj = datetime.datetime.strptime(current_bill_date, "%d-%m-%Y")

        if date_obj.day <= 7:
            return 0.0

        days_late = date_obj.day - 7

        penalty = days_late * penalty_per_day

        return penalty

    except:
        return 0.0

# ---------------- SAVE TO EXCEL ----------------
def save_to_excel(data_dict):

    try:

        new_row = pd.DataFrame([data_dict])

        new_row.columns = new_row.columns.str.strip()

        column_order = [
            "Date",
            "Month",
            "Units",
            "FAC",
            "Bill",
            "Paid",
            "Remaining"
        ]

        new_row = new_row[column_order]

        new_row["Date"] = pd.to_datetime(new_row["Date"], format="%d-%m-%Y")

        if os.path.exists(file_path):

            existing_df = pd.read_excel(file_path)

            existing_df.columns = existing_df.columns.str.strip()

            existing_df["Date"] = pd.to_datetime(
                existing_df["Date"],
                format="%d-%m-%Y",
                errors="coerce"
            )

            combined_df = pd.concat(
                [existing_df, new_row],
                ignore_index=True
            )

        else:

            combined_df = new_row


        # ✅ FIX: Remove duplicate Year-Month entries
        combined_df["YearMonth"] = combined_df["Date"].dt.strftime("%Y-%m")

        combined_df = combined_df.drop_duplicates(
            subset=["YearMonth"],
            keep="last"
        )

        combined_df = combined_df.drop(columns=["YearMonth"])


        combined_df = combined_df.sort_values("Date")

        combined_df["Date"] = combined_df["Date"].dt.strftime("%d-%m-%Y")

        combined_df.to_excel(file_path, index=False)

        print("[SYSTEM] Saved successfully.")

    except Exception as e:
        print("[ERROR saving]", e)

def get_previous_units(current_bill_date):

    if not os.path.exists(file_path):
        return 0.0

    try:

        df = pd.read_excel(file_path)

        df.columns = df.columns.str.strip()

        if df.empty:
            return 0.0

        if "Date" not in df.columns or "Units" not in df.columns:
            return 0.0

        df["Date"] = pd.to_datetime(df["Date"], format="%d-%m-%Y", errors="coerce")

        current_date = datetime.datetime.strptime(current_bill_date, "%d-%m-%Y")

        current_month = current_date.month
        previous_year = current_date.year - 1

        # Find same month previous year
        target_rows = df[
            (df["Date"].dt.month == current_month) &
            (df["Date"].dt.year == previous_year)
        ]

        if target_rows.empty:
            return 0.0

        # If multiple entries exist take latest
        target_rows = target_rows.sort_values("Date")

        previous_units = target_rows.iloc[-1]["Units"]

        return float(previous_units)

    except Exception as e:
        print("[ERROR reading previous year units]", e)
        return 0.0

# ---------------- BILL CALCULATION ----------------
def calculate_bill(units, current_bill_date):

    global adjusted_amount

    # -------- PREVIOUS REMAINING = NET ARREARS --------
    previous_remain = get_previous_remain_amount(current_bill_date)
    net_arrears = previous_remain

    # -------- PENALTY = ADJUSTED AMOUNT --------
    penalty = calculate_penalty()
    adjusted_amount = penalty

    # -------- OTHER CHARGES ALWAYS ZERO --------
    other_charges = 0.0

    # -------- SPIKE CALCULATION (SEPARATE) --------
    spike_adjustment, spike_percent, previous_units = calculate_spike_adjustment(
        units, current_bill_date
    )

    total_energy_charge = 0.0
    slab_details = []

    if units > 0:

        if units <= 100:
            cost = units * 4.28
            total_energy_charge += cost
            slab_details.append(("0-100", units, 4.28, cost))

        else:
            cost = 100 * 4.28
            total_energy_charge += cost
            slab_details.append(("0-100", 100, 4.28, cost))

            if units <= 300:
                cost = (units - 100) * 11.10
                total_energy_charge += cost
                slab_details.append(("101-300", units - 100, 11.10, cost))

            else:
                cost = 200 * 11.10
                total_energy_charge += cost
                slab_details.append(("101-300", 200, 11.10, cost))

                if units <= 500:
                    cost = (units - 300) * 15.38
                    total_energy_charge += cost
                    slab_details.append(("301-500", units - 300, 15.38, cost))

                else:
                    cost = 200 * 15.38
                    total_energy_charge += cost
                    slab_details.append(("301-500", 200, 15.38, cost))

                    remaining_units = units - 500
                    cost = remaining_units * 17.68
                    total_energy_charge += cost
                    slab_details.append(("500+", remaining_units, 17.68, cost))

    # -------- CHARGES --------
    transportation_charge = units * tr_multiplier

    raw_tax = (
        fixed_charge +
        total_energy_charge +
        transportation_charge +
        fac
    ) * raw_tax_percent / 100

    current_bill = (
        fixed_charge +
        total_energy_charge +
        transportation_charge +
        fac +
        raw_tax
    )

    # -------- TOTAL ARREARS --------
    total_arrears_deposit = (
        net_arrears +
        adjusted_amount +
        interest_arrears
    )

    # -------- FINAL PAYABLE --------
    net_amount_payable = (
        current_bill +
        interest +
        total_arrears_deposit
    )

    if pd.isna(net_amount_payable):
        net_amount_payable = 0.0

    rounded_bill = round(float(net_amount_payable) / 10) * 10

    return (
        total_energy_charge,
        transportation_charge,
        raw_tax,
        other_charges,
        current_bill,
        total_arrears_deposit,
        net_amount_payable,
        rounded_bill,
        slab_details,
        spike_adjustment,
        spike_percent,
        previous_units,
        net_arrears
)
# ---------------- DISPLAY ----------------
def display_bill(units, res):

    (
    energy_charge,
    transportation_charge,
    raw_tax,
    other_charges,
    current_bill,
    total_arrears_deposit,
    net_amount_payable,
    rounded_bill,
    slabs,
    spike_adjustment,
    spike_percent,
    previous_units,
    net_arrears
    ) = res

    print("\n=========================================== ELECTRICITY BILL SUMMARY =================================================")
    print("\nSlab Range    Units          Rate (Rs.)     Cost (Rs.)")
    print("------------------------------------------------------------------------------------------------------------------------")

    for s in slabs:
        print(f"{s[0]:<15}{s[1]:<15}{s[2]:<15.2f}{s[3]:<12.2f}")

    print("------------------------------------------------------------------------------------------------------------------------")
    print(f"Bill Month                                                                                                  : {bill_month.upper()}")
    print(f"Bill Date                                                                                                   : {current_bill_date}")
    print(f"Units Consumed                                                                                              : {units}")
    print("\n------------------------------------------------------ PROPOSED SYSTEM ------------------------------------------------\n")
    print(f"Previous Year Same Month Units                                                                              : {previous_units:.0f}")
    print(f"Usage Change                                                                                                : {spike_percent:.2f}%")
    if spike_adjustment > 0:
        print(f"Spike Penalty                                                                                               : {spike_adjustment:.2f}")

    elif spike_adjustment < 0:
        print(f"Saving Reward                                                                                               : {abs(spike_adjustment):.2f}")
    print("\n------------------------------------------------------------------------------------------------------------------------")
    print(f"Fixed Charge                                                                                                : {fixed_charge:.2f}")
    print(f"Electricity Charge                                                                                          : {energy_charge:.2f}")
    print(f"Wheeling Charge({tr_multiplier})                                                                                       : {transportation_charge:.2f}")
    print(f"Fuel Adjustment Charge                                                                                      : {fac:.2f}")
    print(f"Electricity Duty({raw_tax_percent})                                                                                      : {raw_tax:.2f}")
    print(f"Electricity Sales Tax({est})                                                                                  : {est:.2f}")
    print("------------------------------------------------------------------------------------------------------------------------")
    print(f"Other Charges                                                                                               : {other_charges:.2f}")
    print(f"Current Electricity Bill                                                                                    : {current_bill:.2f}")
    print(f"Interest                                                                                                    : {interest:.2f}")
    print(f"Net Arrears / Deposit                                                                                       : {net_arrears:.2f}")
    print(f"Adjusted Amount                                                                                             : {adjusted_amount:.2f}")
    print(f"Interest Arrears                                                                                            : {interest_arrears:.2f}")
    print(f"Total Arrears / Deposit                                                                                     : {total_arrears_deposit:.2f}")
    print(f"Net Amount Payable                                                                                          : {net_amount_payable:.2f}")
    print(f"Rounded Bill Amount                                                                                         : {rounded_bill:.2f}")
    print("------------------------------------------------------------------------------------------------------------------------")
    print(f"TOTAL PAYABLE FOR THIS MONTH                                                                                : {rounded_bill:.2f}")
    print("========================================================================================================================\n")

# ---------------- SHOW USAGE GRAPH ----------------
def show_usage_graph(current_units, current_bill_date):

    try:

        months = []
        units = []
        dates = []

        plt.figure("24 Month Electricity Comparison", figsize=(11, 5))
        plt.clf()

        # -------- LOAD DATA --------
        if os.path.exists(file_path):

            df = pd.read_excel(file_path)

            df.columns = df.columns.str.strip()

            if "Date" in df.columns and "Units" in df.columns:

                df["Date"] = pd.to_datetime(df["Date"], format="%d-%m-%Y", errors="coerce")

                df = df.dropna(subset=["Date", "Units"])

                df = df.sort_values("Date")

                # Remove duplicate month-year
                df["YearMonth"] = df["Date"].dt.strftime("%Y-%m")

                df = df.drop_duplicates(
                    subset=["YearMonth"],
                    keep="last"
                )

                df = df.drop(columns=["YearMonth"])

                # Take last 23 records
                df = df.tail(23)

                for _, row in df.iterrows():
                    dates.append(row["Date"])
                    months.append(row["Date"].strftime("%b-%Y"))
                    units.append(float(row["Units"]))


        # -------- CURRENT MONTH --------
        current_date_obj = datetime.datetime.strptime(current_bill_date, "%d-%m-%Y")

        # Remove same month-year if already present
        filtered_dates = []
        filtered_units = []
        filtered_months = []

        for d, u, m in zip(dates, units, months):

            if not (d.month == current_date_obj.month and d.year == current_date_obj.year):
                filtered_dates.append(d)
                filtered_units.append(u)
                filtered_months.append(m)

        dates = filtered_dates
        units = filtered_units
        months = filtered_months

        # Add current month
        dates.append(current_date_obj)
        units.append(float(current_units))
        months.append(current_date_obj.strftime("%b-%Y"))

        # -------- DRAW GRAPH --------
        plt.figure("24 Month Electricity Comparison", figsize=(11,5))

        x_positions = list(range(len(months)))

        plt.scatter(x_positions, units, s=90)

        global last_slope_line

        # Remove previous slope line
        if last_slope_line is not None:
            try:
                last_slope_line.remove()
            except:
                pass

        idx_current = None
        idx_prev_year = None

        for idx, dt in enumerate(dates):

            if dt.month == current_date_obj.month and dt.year == current_date_obj.year:
                idx_current = idx

            if dt.month == current_date_obj.month and dt.year == current_date_obj.year - 1:
                idx_prev_year = idx

        # -------- DRAW COLORED LINE --------
        if idx_current is not None and idx_prev_year is not None:

            # Determine slope color
            if units[idx_current] > units[idx_prev_year]:
                line_color = "red"   # ascending → aggressive RED
            else:
                line_color = "green" # descending → chill GREEN

            last_slope_line, = plt.plot(
                [x_positions[idx_prev_year], x_positions[idx_current]],
                [units[idx_prev_year], units[idx_current]],
                linewidth=2,
                color=line_color
            )

        # -------- LABELS --------
        plt.xticks(x_positions, months, rotation=45)

        plt.title("Electricity Usage Comparison (Same Month Year-to-Year)")
        plt.xlabel("Month")
        plt.ylabel("Units")

        plt.grid(True)

        plt.tight_layout()

        plt.draw()
        plt.pause(0.1)

    except Exception as e:

        print("Graph error:", e)

# ---------------- INITIALIZE ----------------
current_person_name = None
file_path = os.path.join(base_folder, "EBSfull.xlsx")  # default

# ---------------- MAIN MENU ----------------
while True:

    # ---------- FORCE PROFILE SELECTION FIRST ----------
    while current_person_name is None:
        name = input("Enter Your Name ('r' to retry): ").strip()
        if name.lower() == "r":
            continue

        # Validation
        if not name or name.isdigit():
            print("⚠️ Name cannot be empty or numeric.")
            continue

        parts = name.split()
        if len(parts) != 2 or not all(p.isalpha() for p in parts):
            print("⚠️ Enter full name in format: Firstname Surname (letters only).")
            continue

        first, last = parts
        first = first.capitalize()
        last = last.capitalize()
        current_person_name = f"{first} {last}"
        clean_name = first + last
        file_path = os.path.join(base_folder, f"EBS{clean_name}.xlsx")

        # Load or create profile TXT
        profile_params = create_or_read_profile_txt(current_person_name)

        if not profile_params:
            current_person_name = None
            continue

        # Show profile parameters
        print("\n--- PROFILE DETAILS ---")
        for k, v in profile_params.items():
            print(f"{k}: {v}")

        # Ask user to go to bill or edit profile
        while True:
            print("\nOptions:")
            print("1 - Go to Calculate Bill")
            print("2 - Edit Profile Parameters")
            opt = input("Enter choice (1 or 2): ").strip()
            if opt == "1":
                break  # proceed to main menu / calculate bill
            elif opt == "2":
                # force edit
                profile_params = create_or_read_profile_txt(current_person_name, force_edit=True)
                print("\n--- UPDATED PROFILE DETAILS ---")
                for k, v in profile_params.items():
                    print(f"{k}: {v}")
            else:
                print("⚠️ Invalid choice! Enter 1 or 2.")

    # ---------- SHOW MAIN MENU ----------
    print("\n============================================= MAHAVITRAN CALCULATOR ==================================================")
    print("Current Person :", current_person_name)
    print("1 Calculate Bill")
    print("2 Set Bill Date")
    print("3 Switch Profile")
    print("4 Change Wheeling Charge")
    print("5 Change FAC(Fuel Adjustment Charge)")
    print("6 Change Remaining Amount")
    print("7 Exit")

    choice = input("Enter choice: ").strip()
    if choice not in [str(i) for i in range(1, 9)]:
        print("⚠️ Invalid choice! Please enter a number between 1-7.")
        continue

    # ---------- HANDLE MENU CHOICES ----------
    if choice == "1":  # Calculate Bill
        while True:
            units_input = input("Enter units ('r' to go back): ")
            if units_input.lower() == "r":
                break
            try:
                units = float(units_input)
                break
            except ValueError:
                print("⚠️ Invalid input! Units must be a number.")

        results = calculate_bill(units, current_bill_date)
        show_usage_graph(units, current_bill_date)
        display_bill(units, results)

        while True:
            paid_input = input("Enter paid amount: ")
            try:
                paid = float(paid_input)
                break
            except ValueError:
                print("⚠️ Invalid input! Paid amount must be a number.")

        bill_amount = results[7]
        remain = max(bill_amount - paid, 0.0)

        save_to_excel({
            "Date": current_bill_date,
            "Month": bill_month,
            "Units": units,
            "FAC": fac,
            "Bill": results[7],
            "Paid": paid,
            "Remaining": remain
        })

        plt.close('all')

    elif choice == "2":  # Set Bill Date
        while True:
            date_input = input("Enter date DD-MM-YYYY ('r' to go back): ").strip()
            if date_input.lower() == "r":
                break
            try:
                temp = datetime.datetime.strptime(date_input, "%d-%m-%Y")
                current_bill_date = date_input
                bill_month = temp.strftime("%B")
                break
            except ValueError:
                print("⚠️ Invalid format! Use DD-MM-YYYY (example: 07-04-2026)")

    elif choice == "3":  # Switch Profile
        current_person_name = None
        continue  # go back to profile selection

    elif choice == "4":  # Change Wheeling Charge
        while True:
            tr_input = input("Enter new wheeling charge ('r' to go back): ")
            if tr_input.lower() == "r":
                break
            try:
                tr_multiplier = float(tr_input)
                break
            except ValueError:
                print("⚠️ Invalid input! Wheeling charge must be a number.")

    elif choice == "5":  # Change FAC
        while True:
            fac_input = input("Enter new FAC ('r' to go back): ")
            if fac_input.lower() == "r":
                break
            try:
                fac = float(fac_input)
                break
            except ValueError:
                print("⚠️ Invalid input! FAC must be a number.")

    elif choice == "6":  # Change Net Arrears
        while True:
            arrears_input = input("Enter Net Arrears ('r' to go back): ")
            if arrears_input.lower() == "r":
                break
            try:
                net_arrears = float(arrears_input)
                break
            except ValueError:
                print("⚠️ Invalid input! Net arrears must be a number.")

    elif choice == "7":  # Exit
        print("Exiting...")
        break