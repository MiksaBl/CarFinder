import tkinter as tk
from tkinter import messagebox
import sqlite3
import threading
import time
import requests
from urllib.parse import urlsplit, urlunsplit
from playwright.sync_api import sync_playwright


# =====================================
# TELEGRAM
# =====================================
BOT_TOKEN = "your_bot_token"
CHAT_ID = "your_chat_id"


def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": message
        })
    except Exception as e:
        print("Telegram error:", e)


# =====================================
# DATABASE
# =====================================
conn = sqlite3.connect("radars.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS radars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    url TEXT
)
""")
conn.commit()


# =====================================
# GLOBALS
# =====================================
running = False
seen = {}
checkboxes = []


# =====================================
# CLEAN URL
# =====================================
def clean_url(url):
    try:
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    except:
        return url


# =====================================
# EXTRACT LINKS
# =====================================
def extract_listings(page):
    links = set()

    elements = page.query_selector_all("a")

    for el in elements:
        href = el.get_attribute("href")

        if not href:
            continue

        if "/offers/" in href:

            if href.startswith("/"):
                href = "https://www.autoscout24.com" + href

            links.add(clean_url(href))

    return links


# =====================================
# RADAR LOOP
# =====================================
def radar_loop():

    global running, seen
    running = True
    seen.clear()  # 🔥 FIX

    selected = [x for x in checkboxes if x["var"].get()]

    if not selected:
        messagebox.showerror("Error", "Select at least one radar")
        running = False
        return

    for r in selected:
        seen[r["name"]] = set()  # 🔥 koristi original name

    log("🚗 RADAR STARTED")
    send_telegram("🚗 Radar STARTED")

    first_run = True

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        while running:

            try:

                for r in selected:

                    name = r["name"]  # 🔥 FIX (bez upper)
                    url = r["url"]

                    log(f"🔄 OPEN {name.upper()}")

                    page.goto(url, timeout=60000)
                    page.wait_for_timeout(5000)

                    page.mouse.wheel(0, 4000)
                    time.sleep(2)

                    current = extract_listings(page)

                    new_items = current - seen[name]

                    if first_run:

                        seen[name] = current
                        log(f"📊 {name.upper()} BASELINE: {len(current)}")

                    else:

                        if new_items:

                            for item in list(new_items)[:10]:

                                log("➕ " + item)

                                send_telegram(f"🚗 NEW {name.upper()} FOUND!\n{item}")

                        else:
                            log(f"✔ {name.upper()} no changes")

                        seen[name] = current

                first_run = False

            except Exception as e:
                log(f"ERROR: {e}")

            log("⏳ WAIT 30s...\n")
            time.sleep(30)


# =====================================
# START / STOP
# =====================================
def start():
    t = threading.Thread(target=radar_loop)
    t.daemon = True
    t.start()


def stop():
    global running
    running = False
    log("🛑 STOPPED")


# =====================================
# DB ACTIONS
# =====================================
def add_radar():
    name = name_entry.get()
    url = url_entry.get()

    if not name or not url:
        return

    cursor.execute("INSERT INTO radars(name, url) VALUES (?, ?)", (name, url))
    conn.commit()

    name_entry.delete(0, tk.END)
    url_entry.delete(0, tk.END)

    refresh()


def delete_selected():
    for x in checkboxes:
        if x["var"].get():
            cursor.execute("DELETE FROM radars WHERE id=?", (x["id"],))

    conn.commit()
    refresh()


def refresh():

    for w in radar_frame.winfo_children():
        w.destroy()

    checkboxes.clear()

    cursor.execute("SELECT id, name, url FROM radars")
    rows = cursor.fetchall()

    for r in rows:

        var = tk.BooleanVar()

        cb = tk.Checkbutton(
            radar_frame,
            text=r[1],
            variable=var,
            font=("Segoe UI", 10),
            bg="#0f1115",
            fg="#d0d0d0",
            activebackground="#0f1115",
            activeforeground="#ffffff",
            selectcolor="#1e2430"
        )
        cb.pack(anchor="w")

        checkboxes.append({
            "id": r[0],
            "name": r[1],
            "url": r[2],
            "var": var
        })


# =====================================
# LOG
# =====================================
def log(text):
    logs.insert(tk.END, text + "\n")
    logs.see(tk.END)


# =====================================
# GUI
# =====================================
root = tk.Tk()
root.title("🚗 Auto Radar")
root.geometry("900x700")
root.configure(bg="#0f1115")


title = tk.Label(
    root,
    text="🚗 Auto Radar",
    font=("Segoe UI", 22, "bold"),
    fg="#e6e6e6",
    bg="#0f1115"
)
title.pack(pady=12)


frame = tk.Frame(root, bg="#161a22", padx=10, pady=10)
frame.pack(pady=10)


name_entry = tk.Entry(
    frame,
    font=("Segoe UI", 11),
    bg="#1e2430",
    fg="#ffffff",
    insertbackground="white",
    relief="flat",
    width=25
)
name_entry.grid(row=0, column=0, padx=5)


url_entry = tk.Entry(
    frame,
    width=60,
    font=("Segoe UI", 11),
    bg="#1e2430",
    fg="#ffffff",
    insertbackground="white",
    relief="flat"
)
url_entry.grid(row=0, column=1, padx=5)


tk.Button(
    frame,
    text="ADD",
    command=add_radar,
    bg="#2a7fff",
    fg="white",
    relief="flat",
    padx=10
).grid(row=0, column=2, padx=5)


radar_frame = tk.LabelFrame(
    root,
    text="📦 Saved Radars",
    bg="#0f1115",
    fg="#bdbdbd",
    font=("Segoe UI", 10, "bold"),
    relief="flat"
)
radar_frame.pack(fill="x", padx=12, pady=12)


btn_frame = tk.Frame(root, bg="#0f1115")
btn_frame.pack(pady=10)


tk.Button(btn_frame, text="START", command=start,
          bg="#1f8f4e", fg="white", relief="flat",
          width=12).grid(row=0, column=0, padx=5)

tk.Button(btn_frame, text="STOP", command=stop,
          bg="#b23b3b", fg="white", relief="flat",
          width=12).grid(row=0, column=1, padx=5)

tk.Button(btn_frame, text="DELETE", command=delete_selected,
          bg="#444a55", fg="white", relief="flat",
          width=12).grid(row=0, column=2, padx=5)


logs = tk.Text(
    root,
    bg="#0b0d10",
    fg="#d6d6d6",
    font=("Consolas", 10),
    insertbackground="white",
    relief="flat"
)
logs.pack(fill="both", expand=True, padx=12, pady=12)


refresh()
root.mainloop()