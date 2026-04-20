import datetime
import pandas as pd
import os
import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from tkinter import messagebox, simpledialog, ttk
from tkinter import simpledialog

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
import matplotlib.pyplot as plt

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
import os
import sqlite3
#Admin1a09
# ---------------- DEFAULT VALUES ----------------
current_date_obj = datetime.datetime.now()
current_bill_date = current_date_obj.strftime("%d-%m-%Y")
bill_month = current_date_obj.strftime("%B")
last_slope_line = None
# ---------------- ADMIN LOGIN ----------------
ADMIN_USER = "Admin1a09"
ADMIN_PASS = "Admin1a09"

# ---------------- FILE STORAGE ----------------
base_folder = r"C:\Users\Shreyas Karangutkar\Desktop\EBS Backup\Profiles"
db_path = os.path.join(base_folder, "EBS.db")

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

current_month_units = 0
#------------ CREATE DB ------------------
def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS billing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            month TEXT,
            units REAL,
            fac REAL,
            bill REAL,
            paid REAL,
            remaining REAL
        )
    """)

    conn.commit()
    conn.close()
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

            stored_password = profile_data.get("Password", "")

            for _ in range(3):
                entered_password = simpledialog.askstring(
                    "Password",
                    f"Enter password for {person_name}",
                    show="*"
                )

                if entered_password is None:
                    return {}

                if entered_password == stored_password:
                    return profile_data
                else:
                    messagebox.showerror("Error", "Wrong password")

            messagebox.showerror("Error", "Too many wrong attempts")
            return {}

        except Exception as e:
            messagebox.showerror("Error", f"Profile read error\n{e}")
            return {}
        
# ---------- CREATE NEW PROFILE ----------
    profile_data = create_profile_popup(person_name)

    if not profile_data:
        return {}

    try:
        with open(txt_file, "w") as f:
            f.write(f"Name: {person_name}\n")
            f.write(f"Password: {profile_data['Password']}\n")

            for key in ["Address", "Gender", "Age", "Family Members"]:
                f.write(f"{key}: {profile_data[key]}\n")

    except Exception as e:
        messagebox.showerror("Error", f"Save error\n{e}")

    return profile_data

def create_profile_popup(person_name):

    popup = tk.Toplevel()
    popup.title("Create New Profile")
    popup.geometry("350x350")
    popup.grab_set()

    tk.Label(popup, text=f"New Profile: {person_name}",
             font=("Arial", 12, "bold")).pack(pady=5)

    frame = tk.Frame(popup)
    frame.pack(pady=5)

    # -------- Fields --------
    labels = ["Password", "Confirm Password", "Address",
              "Gender", "Age", "Family Members"]

    entries = {}

    for i, label in enumerate(labels):
        tk.Label(frame, text=label).grid(row=i, column=0, sticky="w")

        show = "*" if "Password" in label else None
        entry = tk.Entry(frame, show=show, width=22)
        entry.grid(row=i, column=1, pady=2)

        entries[label] = entry

    result = {}

    def submit():

        password = entries["Password"].get()
        confirm = entries["Confirm Password"].get()
        address = entries["Address"].get()
        gender = entries["Gender"].get().strip().lower()
        if gender in ["m", "male"]:
            gender = "Male"
        elif gender in ["f", "female"]:
            gender = "Female"
        else:
            messagebox.showerror("Error", "Enter Male/Female or M/F")
            return
        age = entries["Age"].get()
        family = entries["Family Members"].get()

        if len(password) < 4:
            messagebox.showerror("Error", "Password too short")
            return

        if password != confirm:
            messagebox.showerror("Error", "Passwords don't match")
            return

        if len(address.split()) < 5:
            messagebox.showerror("Error", "Invalid address")
            return

        if not age.isdigit():
            messagebox.showerror("Error", "Invalid age")
            return
        
        if not family.isdigit():
            messagebox.showerror("Error", "Family members must be a number")
            return

        family = int(family)

        if family < 0 or family > 20:
            messagebox.showerror("Error", "Family members must be 0–20")
            return

        result["Password"] = password
        result["Address"] = address
        result["Gender"] = gender
        result["Age"] = age
        result["Family Members"] = family

        popup.destroy()

    tk.Button(popup, text="Create Profile",
              command=submit).pack(pady=10)

    popup.wait_window()

    return result

# ---------------- GET LAST REMAIN AMOUNT ----------------
def get_previous_remain_amount(current_bill_date):

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT remaining 
        FROM billing
        WHERE date < ?
        ORDER BY date DESC
        LIMIT 1
    """, (current_bill_date,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return float(row[0])

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

# ---------------- SAVE TO DB ----------------
def save_to_db(data_dict):

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO billing (date, month, units, fac, bill, paid, remaining)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        data_dict["Date"],
        data_dict["Month"],
        data_dict["Units"],
        data_dict["FAC"],
        data_dict["Bill"],
        data_dict["Paid"],
        data_dict["Remaining"]
    ))

    conn.commit()
    conn.close()
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

    global adjusted_amount, net_arrears

    # ---------------- PREVIOUS REMAIN → ARREARS ----------------
    previous_remain = get_previous_remain_amount(current_bill_date)
    net_arrears = previous_remain

    # ---------------- PENALTY ----------------
    penalty = calculate_penalty()
    adjusted_amount = penalty

    # ---------------- OTHER CHARGES ----------------
    # Other charges always zero (shown separately)
    other_charges = 0.0

    spike_adjustment, spike_percent, previous_units = calculate_spike_adjustment(
        units, current_bill_date
)
    # ---------------- SLAB CALCULATION ----------------
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

    # ---------------- CHARGES ----------------
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

    # ---------------- ARREARS TOTAL ----------------
    total_arrears_deposit = (
        net_arrears +      # previous remaining
        adjusted_amount +  # penalty
        interest_arrears
    )

    # ---------------- FINAL PAYABLE ----------------
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
        previous_units
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
        previous_units
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
        graph_path = os.path.join(base_folder, "temp_graph.png")
        plt.savefig(graph_path)
        plt.draw()
        plt.pause(0.1)

    except Exception as e:

        print("Graph error:", e)

# ---------------- INITIALIZE ----------------
current_person_name = None
file_path = os.path.join(base_folder, "EBSfull.xlsx")  # default

class ElectricityApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Electricity Billing System")
        self.root.geometry("900x650")

        self.root.state("zoomed")   # 👈 ADD THIS

        self.current_person_name = None
        self.create_login_screen()

    # ---------------- COMMON ----------------
    def clear_window(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def add_back_button(self, command):
        tk.Button(self.root,
                  text="⬅ Back",
                  command=command).place(x=800, y=10)

    # ---------------- LOGIN SCREEN ----------------
    def create_login_screen(self):

        self.clear_window()

        frame = tk.Frame(self.root)
        frame.pack(expand=True)

        tk.Label(frame, text="ENTER CUSTOMER NAME",
                 font=("Arial", 18, "bold")).pack(pady=10)

        tk.Label(frame, text="Full Name").pack()
        self.name_entry = tk.Entry(frame, width=30)
        self.name_entry.pack()

        tk.Button(frame, text="Login",
                  command=self.login).pack(pady=5)

        tk.Button(frame,
                  text="Admin Settings 🔐",
                  width=20,
                  command=self.admin_login).pack(pady=5)
        
    def save_payment(self):

        global last_rounded_bill

        try:
            paid = float(self.paid_entry.get())
        except:
            messagebox.showerror("Error", "Enter valid paid amount")
            return

        try:
            units = float(self.units_entry.get())
        except:
            messagebox.showerror("Error", "Units missing")
            return

        remaining = last_rounded_bill - paid

        data_dict = {
            "Date": current_bill_date,
            "Month": bill_month,
            "Units": units,
            "FAC": fac,
            "Bill": last_rounded_bill,
            "Paid": paid,
            "Remaining": remaining
        }

        save_to_db(data_dict)
        messagebox.showinfo("Saved", "Payment Saved Successfully")

        # CREATE PDF
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        try:
                profile_name = self.current_person_name.replace(" ", "")
                graph_path = os.path.join(base_folder, "temp_graph.png")

                print("[DEBUG] Creating PDF...")

                create_pdf(profile_name, self.last_bill_result, graph_path, paid)

                print("[DEBUG] PDF Created Successfully")
                messagebox.showinfo("Created", "PDF Created Sucessfully")

        except Exception as e:
                import traceback
                traceback.print_exc()
                messagebox.showerror("PDF Error", str(e))

    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
    from reportlab.lib.styles import getSampleStyleSheet

    # ---------------- LOGIN ----------------
    def login(self):

        name = self.name_entry.get().strip()

        if not name:
            messagebox.showerror("Error", "Enter Name")
            return

        global file_path

        parts = name.split()
        if len(parts) != 2:
            messagebox.showerror("Error", "Enter Firstname Surname")
            return

        first, last = parts
        first = first.capitalize()
        last = last.capitalize()

        self.current_person_name = f"{first} {last}"
        clean_name = first + last

        file_path = os.path.join(base_folder, f"EBS{clean_name}.xlsx")

        profile = create_or_read_profile_txt(self.current_person_name)

        if not profile:
            return

        self.profile_data = profile
        self.create_main_menu()

    # ---------------- MAIN MENU ----------------
    def create_main_menu(self):

        self.clear_window()

        self.add_back_button(self.create_login_screen)

        tk.Label(self.root,
                 text=f"Welcome {self.current_person_name}",
                 font=("Arial", 14, "bold")).pack(pady=5)

        if hasattr(self, "profile_data"):

            info_frame = tk.Frame(self.root)
            info_frame.pack(pady=5)

            tk.Label(info_frame,
                     text=f"Address : {self.profile_data.get('Address','N/A')}").pack()

            tk.Label(info_frame,
                     text=f"Gender : {self.profile_data.get('Gender','N/A')}").pack()

            tk.Label(info_frame,
                     text=f"Age : {self.profile_data.get('Age','N/A')}").pack()

            tk.Label(info_frame,
                     text=f"Family Members : {self.profile_data.get('Family Members','N/A')}").pack()

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=20)

        tk.Button(btn_frame,
                  text="Calculate Bill",
                  width=25,
                  command=self.calculate_screen).grid(row=0, column=0, pady=5)

        tk.Button(btn_frame,
                  text="Switch Profile",
                  width=25,
                  command=self.create_login_screen).grid(row=1, column=0, pady=5)

    # ---------------- CALCULATE SCREEN ----------------
    def calculate_screen(self):

        self.clear_window()
        self.add_back_button(self.create_main_menu)

        # ================= TITLE =================
        tk.Label(
            self.root,
            text="Calculate Bill",
            font=("Arial", 16, "bold")
        ).pack(pady=8)

        # ================= MAIN CONTAINER =================
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill="both", expand=True)

        # ================= INPUT SECTION =================
        input_frame = tk.Frame(main_frame)
        input_frame.pack(pady=5)

        tk.Label(input_frame, text="Units").grid(row=0, column=0, padx=5)

        self.units_entry = tk.Entry(input_frame, width=15)
        self.units_entry.grid(row=0, column=1, padx=5)

        tk.Button(
            input_frame,
            text="Calculate",
            command=self.calculate_bill_gui
        ).grid(row=0, column=2, padx=10)

        # ================= PAYMENT SECTION (HIDDEN INITIALLY, ABOVE SCROLL) =================
        self.payment_frame = tk.Frame(main_frame)

        tk.Label(self.payment_frame, text="Paid Amount").pack(side="left", padx=5)

        self.paid_entry = tk.Entry(self.payment_frame, width=15)
        self.paid_entry.pack(side="left", padx=5)

        tk.Button(
            self.payment_frame,
            text="Save Data",
            command=self.save_payment
        ).pack(side="left", padx=5)

        # DO NOT PACK YET (hidden)

        # ================= SCROLL AREA =================
        scroll_container = tk.Frame(main_frame)
        scroll_container.pack(fill="both", expand=True, padx=10, pady=5)

        # fixed height behavior (prevents layout pushing)
        scroll_container.pack_propagate(False)

        self.bill_canvas = tk.Canvas(scroll_container)

        scrollbar = ttk.Scrollbar(
            scroll_container,
            orient="vertical",
            command=self.bill_canvas.yview
        )

        self.scroll_frame = tk.Frame(self.bill_canvas)

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self.bill_canvas.configure(
                scrollregion=self.bill_canvas.bbox("all")
            )
        )

        self.bill_canvas.create_window(
            (0, 0),
            window=self.scroll_frame,
            anchor="nw"
        )

        self.bill_canvas.configure(yscrollcommand=scrollbar.set)

        self.bill_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # ================= ENSURE PAYMENT IS HIDDEN =================
        if hasattr(self, "payment_frame"):
            self.payment_frame.pack_forget()
        
    def calculate_bill_gui(self):
        global current_month_units

        # ---------- INPUT VALIDATION ----------
        try:
            current_month_units = float(self.units_entry.get())
        except:
            messagebox.showerror("Error", "Enter valid units")
            return

        units = current_month_units

        # ---------- BILL CALCULATION ----------
        results = calculate_bill(units, current_bill_date)

        # ---------- GRAPH ----------
        try:
            show_usage_graph(units, current_bill_date)
        except Exception as e:
            print("Graph error:", e)

        # ---------- DISPLAY ----------
        self.display_bill_gui(units, results)
        self.last_bill_result = results

        # ---------- SHOW PAYMENT SECTION ----------
        if hasattr(self, "payment_frame"):
            self.payment_frame.pack(pady=5)

    def display_bill_gui(self, units, res):

        global last_rounded_bill
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        row = 0

        def add_line(text):
            nonlocal row
            tk.Label(self.scroll_frame,
                    text=text,
                    anchor="w",
                    font=("Consolas", 10)
                    ).grid(row=row, column=0, sticky="w")
            row += 1

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
            previous_units
        ) = res

        last_rounded_bill = rounded_bill

        add_line("ELECTRICITY BILL SUMMARY")
        add_line("----------------------------------")

        for s in slabs:
            add_line(f"{s[0]} | Units:{s[1]} | Rate:{s[2]} | Cost:{s[3]}")

        add_line(f"Units: {units}")
        add_line(f"Fixed Charge: {fixed_charge}")
        add_line(f"Energy Charge: {energy_charge}")
        add_line(f"Wheeling: {transportation_charge}")
        add_line(f"FAC: {fac}")
        add_line(f"Duty: {raw_tax}")
        add_line(f"Other Charges: {other_charges}")
        add_line(f"Current Bill: {current_bill}")
        add_line(f"Interest: {interest}")
        add_line(f"Arrears: {net_arrears}")
        add_line(f"Adjusted: {adjusted_amount}")
        add_line(f"Total Arrears: {total_arrears_deposit}")
        add_line(f"Net Payable: {net_amount_payable}")
        add_line(f"Rounded Bill: {rounded_bill}")

        add_line("------ USAGE ANALYSIS ------")
        add_line(f"Previous Year Units: {previous_units:.0f}")
        add_line(f"Usage Change: {spike_percent:.2f}%")

        if spike_adjustment > 0:
            add_line(f"Spike Penalty: ₹{spike_adjustment:.2f}")
        elif spike_adjustment < 0:
            add_line(f"Saving Reward: ₹{abs(spike_adjustment):.2f}")
        else:
            add_line("Spike Adjustment: None")


    # ---------------- ADMIN ----------------
    def admin_login(self):

        popup = tk.Toplevel(self.root)
        popup.title("Admin Login")
        popup.geometry("250x180")
        popup.grab_set()

        tk.Label(popup,
                text="Admin Login",
                font=("Arial", 12, "bold")).pack(pady=5)

        tk.Label(popup, text="Admin ID").pack()
        user_entry = tk.Entry(popup)
        user_entry.pack()

        tk.Label(popup, text="Password").pack()
        pass_entry = tk.Entry(popup, show="*")
        pass_entry.pack()

        def verify():
            if user_entry.get() == ADMIN_USER and pass_entry.get() == ADMIN_PASS:
                popup.destroy()
                self.admin_menu()
            else:
                messagebox.showerror("Error", "Invalid Admin Credentials")

        tk.Button(popup, text="Login", command=verify).pack(pady=8)

    def admin_menu(self):

        self.admin_popup = tk.Toplevel(self.root)   # <-- store reference
        self.admin_popup.title("Admin Controls")
        self.admin_popup.geometry("300x230")
        self.admin_popup.grab_set()

        tk.Label(self.admin_popup,
                text="Admin Controls",
                font=("Arial", 12, "bold")).pack(pady=10)

        tk.Button(self.admin_popup,
                text="Change Wheeling",
                width=22,
                command=self.change_wheeling).pack(pady=5)

        tk.Button(self.admin_popup,
                text="Change FAC",
                width=22,
                command=self.change_fac).pack(pady=5)

        tk.Button(self.admin_popup,
        text="Change Arrears",
        width=22,
        command=self.change_arrears).pack(pady=5)

        tk.Button(self.admin_popup,
                text="Change Bill Date",
                width=22,
                command=self.change_bill_date).pack(pady=5)

    # ---------------- CHANGE OPTIONS ----------------
    def change_fac(self):
        global fac
        value = simpledialog.askfloat(
            "FAC",
            "Enter new FAC",
            parent=self.admin_popup   # <-- change
        )
        if value is not None:
            fac = value


    def change_wheeling(self):
        global tr_multiplier
        value = simpledialog.askfloat(
            "Wheeling",
            "Enter rate per unit",
            parent=self.admin_popup   # <-- change
        )
        if value is not None:
            tr_multiplier = value

    def change_arrears(self):
        global net_arrears
        value = simpledialog.askfloat(
            "Arrears",
            "Enter Net Arrears",
            parent=self.admin_popup
        )
        if value is not None:
            net_arrears = value
    
    def change_bill_date(self):

        global current_bill_date, current_date_obj, bill_month

        new_date = simpledialog.askstring(
            "Bill Date",
            "Enter new bill date (DD-MM-YYYY):",
            parent=self.admin_popup   # ✅ keep admin menu active
        )

        # Cancel pressed
        if new_date is None:
            return

        new_date = new_date.strip()

        # -------- VALIDATION --------
        try:
            date_obj = datetime.datetime.strptime(new_date, "%d-%m-%Y")
        except ValueError:
            messagebox.showerror(
                "Invalid Date",
                "Wrong format! Use DD-MM-YYYY",
                parent=self.admin_popup
            )
            return

        # prevent future date
        if date_obj > datetime.datetime.now():
            messagebox.showerror(
                "Invalid Date",
                "Future dates not allowed",
                parent=self.admin_popup
            )
            return

        # -------- UPDATE --------
        current_bill_date = new_date
        current_date_obj = date_obj
        bill_month = date_obj.strftime("%B")

        messagebox.showinfo(
            "Success",
            f"Bill Date Updated To:\n{current_bill_date}",
            parent=self.admin_popup
        )

def create_pdf(profile_name, bill_data, graph_path, paid):

    bill_month_year = current_date_obj.strftime("%B-%Y")
    pdf_path = os.path.join(base_folder, f"{profile_name}-{bill_month_year}.pdf")

    # FORCE REPLACE EXISTING FILE
    try:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
    except:
        pass

    styles = getSampleStyleSheet()
    content = []

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
        previous_units
    ) = bill_data

    # -------- TITLE --------
    content.append(Paragraph("ELECTRICITY BILL SUMMARY", styles["Title"]))
    content.append(Spacer(1, 10))

    # -------- BASIC --------
    content.append(Paragraph(f"Bill Month : {bill_month}", styles["Normal"]))
    content.append(Paragraph(f"Bill Date : {current_bill_date}", styles["Normal"]))
    content.append(Paragraph(f"Units Consumed : {current_month_units}", styles["Normal"]))
    content.append(Spacer(1, 10))

    # -------- SLABS --------
    content.append(Paragraph("SLAB DETAILS", styles["Heading2"]))
    for s in slabs:
        content.append(Paragraph(
            f"{s[0]} | Units:{s[1]} | Rate:{s[2]} | Cost:{s[3]}",
            styles["Normal"]
        ))

    content.append(Spacer(1, 10))

    # -------- USAGE --------
    content.append(Paragraph("USAGE ANALYSIS", styles["Heading2"]))
    content.append(Paragraph(f"Previous Year Units : {previous_units}", styles["Normal"]))
    content.append(Paragraph(f"Usage Change : {spike_percent:.2f}%", styles["Normal"]))

    if spike_adjustment > 0:
        content.append(Paragraph(f"Spike Penalty : {spike_adjustment}", styles["Normal"]))
    elif spike_adjustment < 0:
        content.append(Paragraph(f"Saving Reward : {abs(spike_adjustment)}", styles["Normal"]))

    content.append(Spacer(1, 10))

    # -------- CHARGES --------
    content.append(Paragraph("CHARGES", styles["Heading2"]))
    content.append(Paragraph(f"Fixed Charge : {fixed_charge}", styles["Normal"]))
    content.append(Paragraph(f"Electricity Charge : {energy_charge}", styles["Normal"]))
    content.append(Paragraph(f"Wheeling Charge : {transportation_charge}", styles["Normal"]))
    content.append(Paragraph(f"FAC : {fac}", styles["Normal"]))
    content.append(Paragraph(f"Electricity Duty : {raw_tax}", styles["Normal"]))
    

    content.append(Spacer(1, 10))

    # -------- ARREARS --------
    content.append(Paragraph("ARREARS", styles["Heading2"]))
    content.append(Paragraph(f"Other Charges : {other_charges}", styles["Normal"]))
    content.append(Paragraph(f"Current Bill : {current_bill}", styles["Normal"]))
    content.append(Paragraph(f"Interest : {interest}", styles["Normal"]))
    content.append(Paragraph(f"Net Arrears : {net_arrears}", styles["Normal"]))
    content.append(Paragraph(f"Adjusted Amount : {adjusted_amount}", styles["Normal"]))
    content.append(Paragraph(f"Interest Arrears : {interest_arrears}", styles["Normal"]))
    content.append(Paragraph(f"Total Arrears : {total_arrears_deposit}", styles["Normal"]))

    content.append(Spacer(1, 10))

    # -------- FINAL --------
    content.append(Paragraph("FINAL SUMMARY", styles["Heading2"]))
    content.append(Paragraph(f"Net Amount Payable : {net_amount_payable}", styles["Normal"]))
    content.append(Paragraph(f"Rounded Bill : {rounded_bill}", styles["Normal"]))
    content.append(Paragraph(f"Amount Paid : {paid}", styles["Normal"]))
    content.append(Paragraph(f"Balance Remaining : {rounded_bill - paid}", styles["Normal"]))

    content.append(Spacer(1, 15))

    # -------- GRAPH --------
    if os.path.exists(graph_path):
        content.append(Paragraph("USAGE GRAPH", styles["Heading2"]))
        content.append(Image(graph_path, width=420, height=250))

    doc = SimpleDocTemplate(pdf_path)
    doc.build(content)

    print("PDF saved:", pdf_path)

# ---------- MAIN ----------
if __name__ == "__main__":
    init_db()
    root = tk.Tk()
    root.title("Electricity Billing System")
    root.geometry("500x650")   # optional

    app = ElectricityApp(root)

    root.mainloop()