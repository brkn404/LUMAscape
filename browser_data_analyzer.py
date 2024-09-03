import os
import sqlite3
import json
import datetime
import csv
import glob
import shutil
from tkinter import Tk, filedialog, messagebox, StringVar, Label, Button, OptionMenu
from urllib.parse import urlparse
import matplotlib.pyplot as plt

# Temporary directory to store copies of Firefox database files
TEMP_DIR = os.path.expanduser("~/temp_firefox_data")

def setup_temp_dir():
    """Ensure that the temporary directory exists."""
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)

def copy_firefox_files(profile_path):
    """
    Copy the Firefox cookies.sqlite and places.sqlite files to a temporary directory.

    Args:
        profile_path (str): Path to the Firefox profile directory.
    """
    try:
        shutil.copy(os.path.join(profile_path, "cookies.sqlite"), TEMP_DIR)
        shutil.copy(os.path.join(profile_path, "places.sqlite"), TEMP_DIR)
        print("Firefox database files copied to temporary directory.")
    except Exception as e:
        print(f"Error copying Firefox files: {e}")

# Utility functions for database connection and data extraction

def get_browser_paths(browser_name):
    if browser_name == "chrome":
        return {
            "cookies": os.path.expanduser("~/.config/google-chrome/Default/Cookies"),
            "history": os.path.expanduser("~/.config/google-chrome/Default/History")
        }
    elif browser_name == "firefox":
        # Locate the Firefox profile path and copy necessary files to TEMP_DIR
        profile_path_pattern = os.path.expanduser("~/Library/Application Support/Firefox/Profiles/sfjxgd2e.default-release")
        profile_dirs = glob.glob(profile_path_pattern)
        if profile_dirs:
            profile_path = profile_dirs[0]
            setup_temp_dir()
            copy_firefox_files(profile_path)
            return {
                "cookies": os.path.join(TEMP_DIR, "cookies.sqlite"),
                "history": os.path.join(TEMP_DIR, "places.sqlite")
            }
        else:
            raise ValueError("Firefox profile not found. Ensure Firefox is installed and run at least once.")
    else:
        raise ValueError("Unsupported browser")

def read_cookies(cookies_db):
    try:
        conn = sqlite3.connect(f"file:{cookies_db}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute("SELECT host_key, name, value, creation_utc, last_access_utc, expires_utc FROM cookies")

        cookies = []
        for host, name, value, creation, last_access, expires in cursor.fetchall():
            cookies.append({
                "host": host,
                "name": name,
                "value": value,
                "creation": datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=creation),
                "last_access": datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=last_access),
                "expires": datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=expires) if expires != 0 else "Session"
            })
        conn.close()
        return cookies
    except sqlite3.OperationalError as e:
        print(f"Error reading cookies: {e}")
        return []

def read_history(history_db):
    try:
        conn = sqlite3.connect(f"file:{history_db}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute("SELECT url, title, visit_count, last_visit_time FROM urls")

        history = []
        for url, title, visit_count, last_visit_time in cursor.fetchall():
            history.append({
                "url": url,
                "title": title,
                "visit_count": visit_count,
                "last_visit": datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=last_visit_time)
            })
        conn.close()
        return history
    except sqlite3.OperationalError as e:
        print(f"Error reading history: {e}")
        return []

# Cookie categorization function

def categorize_cookies(cookies):
    tracking_domains = ["google-analytics.com", "doubleclick.net", "facebook.com"]
    categorized_cookies = {
        "tracking": [],
        "first_party": [],
        "third_party": [],
        "session": [],
        "persistent": []
    }

    for cookie in cookies:
        if any(domain in cookie['host'] for domain in tracking_domains):
            categorized_cookies["tracking"].append(cookie)
        if cookie['expires'] == "Session":
            categorized_cookies["session"].append(cookie)
        else:
            categorized_cookies["persistent"].append(cookie)

        # First-party vs. third-party detection based on host
        if urlparse(cookie['host']).hostname == cookie['host']:
            categorized_cookies["first_party"].append(cookie)
        else:
            categorized_cookies["third_party"].append(cookie)

    return categorized_cookies

# Export and reporting functions

def export_data(cookies, history, output_format="csv"):
    try:
        if not cookies and not history:
            print("No data to export.")
            return

        if output_format == "csv":
            if cookies:
                with open("cookies.csv", "w", newline='') as csvfile:
                    fieldnames = cookies[0].keys()
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    for cookie in cookies:
                        writer.writerow(cookie)

            if history:
                with open("history.csv", "w", newline='') as csvfile:
                    fieldnames = history[0].keys()
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    for entry in history:
                        writer.writerow(entry)
        elif output_format == "json":
            if cookies:
                with open("cookies.json", "w") as jsonfile:
                    json.dump(cookies, jsonfile, indent=4, default=str)

            if history:
                with open("history.json", "w") as jsonfile:
                    json.dump(history, jsonfile, indent=4, default=str)
        print("Data exported successfully.")
    except Exception as e:
        print(f"Error exporting data: {e}")

def generate_report(cookies, history):
    try:
        domain_counts = {}
        for entry in history:
            domain = urlparse(entry["url"]).netloc
            if domain in domain_counts:
                domain_counts[domain] += 1
            else:
                domain_counts[domain] = 1

        if domain_counts:
            domains = list(domain_counts.keys())
            counts = list(domain_counts.values())
            plt.bar(domains, counts)
            plt.xlabel("Domain")
            plt.ylabel("Visit Count")
            plt.title("Most Visited Domains")
            plt.xticks(rotation=90)
            plt.tight_layout()
            plt.savefig("visit_report.png")
            plt.show()
        else:
            print("No data available to generate report.")
    except Exception as e:
        print(f"Error generating report: {e}")

# GUI setup using Tkinter

def run_analysis():
    try:
        browser = browser_var.get()
        paths = get_browser_paths(browser)

        cookies = read_cookies(paths["cookies"])
        if not cookies:
            print("No cookies found or unable to read cookies.")
        
        history = read_history(paths["history"])
        if not history:
            print("No browsing history found or unable to read history.")
        
        # Proceed with data categorization, export, and report generation if data exists
        if cookies or history:
            categorized_cookies = categorize_cookies(cookies)
            export_data(categorized_cookies["tracking"], history)
            generate_report(categorized_cookies["tracking"], history)
            messagebox.showinfo("Analysis Complete", "Data analysis and export completed successfully.")
        else:
            messagebox.showwarning("No Data", "No cookies or history data available for analysis.")
    except Exception as e:
        print(f"An error occurred during analysis: {e}")
        messagebox.showerror("Error", f"An error occurred: {e}")

# Main GUI application

root = Tk()
root.title("Browser Data Analyzer")

browser_var = StringVar(root)
browser_var.set("chrome")  # default value

label = Label(root, text="Select Browser:")
label.pack()

browser_menu = OptionMenu(root, browser_var, "chrome", "firefox")
browser_menu.pack()

analyze_button = Button(root, text="Run Analysis", command=run_analysis)
analyze_button.pack()

root.mainloop()
