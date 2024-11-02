import os
import sys
import asyncio
import aiohttp
import tkinter as tk
from tkinter import scrolledtext, font, filedialog, messagebox
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import pandas as pd
import webbrowser
import win32print
import win32api
import tkinter.simpledialog as simpledialog
import threading
import time
from tkinter import ttk
import matplotlib.pyplot as plt  # Import matplotlib for plotting
import gc
import tkinter.simpledialog as simpledialog
import threading
from tkinter import Scrollbar
import tkinter.ttk as ttk
import asyncio
import matplotlib.pyplot as plt
from aiohttp import ClientSession, ClientTimeout, TCPConnector
# Efter en stor operation
gc.collect()



























# Standardvärden för halvfart
default_max_concurrent_requests = 2.2
default_delay_time = 2.5

# Globala variabler för nuvarande inställningar
max_concurrent_requests = default_max_concurrent_requests
delay_time = default_delay_time




upload_task = None  # To keep track of the background task
auto_upload_enabled = False  # To track whether auto-upload is enabled
upload_interval = 20000  # Default update interval in milliseconds (20 seconds)
current_font_size = 10  # Default font size
result_font = ("Courier", current_font_size)  # Use a monospaced font to maintain layout
only_unfinished = False  # Global flag to track if we should only show unfinished races
selected_items_global = []

# Create show_trend_graph after root window is initialized
show_trend_graph = None

# Determine the base path for resources
if hasattr(sys, '_MEIPASS'):
    base_path = sys._MEIPASS
else:
    base_path = os.path.abspath(".")

ico_path = os.path.join(base_path, 'myicon.ico')

async def fetch_main_page_links():
    url = "https://jokkis.net/online2/index.php"
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Virhe päivitettäessä pääsivua: {e}")
        return []

    soup = BeautifulSoup(response.content, "html.parser")
    links = []
    
    date_pattern = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")
    
    for link in soup.find_all("a", href=True):
        if "kisa.php" in link['href']:
            full_url = requests.compat.urljoin(url, link['href'])
            link_text = link.get_text(strip=True)
            date_match = date_pattern.search(link_text)
            if date_match:
                day, month, year = map(int, date_match.groups())
                race_date = datetime(year, month, day)
                links.append((link_text, full_url, race_date))

    links.sort(key=lambda x: x[2], reverse=True)
    return links

async def fetch_all_links(session, url):
    try:

        headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}
        async with session.get(url) as response:
            content = await response.text()
            soup = BeautifulSoup(content, "html.parser")
            links = soup.find_all("a", href=True)

            valid_links = []
            for link in links:
                if "lahto_selailu.php" in link['href']:
                    full_url = requests.compat.urljoin(url, link['href'])
                    valid_links.append(full_url)

            if len(valid_links) > 20:
                await asyncio.sleep(0.2)  # Add delay to avoid server overload
                
            return valid_links

    except Exception as e:
        result_text.insert(tk.END, f"Virhe päivitettäessä pääsivua: {e}\n")
        return []



def clear_flag_summary():
    """Rensar innehållet i flaggsammanfattningsfönstret."""
    if 'flag_text' in globals() and flag_text is not None:
        flag_text.delete(1.0, tk.END)  # Rensa all text i flag_text






def update_font_size(new_size):
    global result_font
    result_font = ("Courier", int(new_size))  # Uppdatera fontstorleken
    result_text.config(font=result_font)  # Tillämpa på result_text

    # Kontrollera om flag_text är definierad och uppdatera dess fontstorlek
    if 'flag_text' in globals() and flag_text is not None:
        flag_text.config(font=result_font)  # Tillämpa på flag_text också

def extract_full_race_details(race_element):
    race_details = race_element.get_text(strip=True)
    current_element = race_element
    while current_element.next_sibling:
        current_element = current_element.next_sibling
        if isinstance(current_element, str):
            race_details += f" {current_element.strip()}"
        elif current_element.name and "table" not in current_element.name:
            race_details += f" {current_element.get_text(strip=True)}"
        else:
            break
    return race_details.strip()

# Funktion för att extrahera startnumret från race_details
def extract_race_number(race_details):
    match = re.search(r'Lähtö n:o (\d+)', race_details)
    return int(match.group(1)) if match else None





async def fetch_filtered_drivers(session, url, filter_text, driver_counter, race_name, only_unfinished, all_found_entries, positions, selected_heat_types, flag_counter, driver_flag_counter, semaphore, delay_time=1.0):
    max_retries = 3  # Maximum number of retries
    async with semaphore:  # Limit concurrent requests
        for attempt in range(max_retries):
            try:
                async with session.get(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
                }) as response:
                    if response.status != 200:
                        raise Exception(f"Unexpected status code: {response.status}")
                    
                    content = await response.text()
                    soup = BeautifulSoup(content, "html.parser")
                    race_elements = soup.find_all(string=lambda text: "Lähtö n:o" in text)
                    filter_text = filter_text.strip().lower()  # Normalize filter_text to lowercase for comparison

                    # Split the filter_text into parts for first and last name handling
                    filter_parts = filter_text.split()
                    if len(filter_parts) == 2:
                        # Create two search patterns for "First Last" and "Last First"
                        first_last_pattern = f"{filter_parts[0]} {filter_parts[1]}"
                        last_first_pattern = f"{filter_parts[1]} {filter_parts[0]}"
                    else:
                        # If only one part (or not exactly two), fallback to matching as-is
                        first_last_pattern = filter_text
                        last_first_pattern = None

                    for race_element in race_elements:
                        race_details = extract_full_race_details(race_element)
                        race_number = extract_race_number(race_details)

                        if race_number is None:
                            continue

                        heat_type = race_details.split(" / ")[-1].strip()

                        # Filter by selected heat types if applicable
                        if selected_heat_types and not any(re.search(re.escape(ht), heat_type) for ht in selected_heat_types):
                            continue

                        race_table = race_element.find_next("table")
                        if race_table:
                            rows = race_table.find_all("tr")
                            race_entries = []
                            at_least_one_unfinished = False
                            include_race = False

                            for row in rows:
                                columns = row.find_all("td")
                                if len(columns) >= 6:
                                    driver_name = columns[2].text.strip().lower()
                                    car_name = columns[4].text.strip().lower()

                                    # Check for name match in both "First Last" and "Last First" formats
                                    if (driver_name == first_last_pattern or
                                        (last_first_pattern and driver_name == last_first_pattern) or
                                        car_name == filter_text):
                                        include_race = True
                                        print(f"Match found: '{filter_text}' in '{driver_name}' or '{car_name}'")

                                    race_entries.append([col.text.strip() for col in columns])

                                    if not columns[5].text.strip():
                                        at_least_one_unfinished = True

                                    flags = columns[5].text.strip().split()
                                    driver_flag_counter.setdefault(driver_name, {"starts": 0})
                                    driver_flag_counter[driver_name]["starts"] += 1
                                    for flag in flags:
                                        if flag not in ['S'] and flag.isalpha():
                                            driver_flag_counter[driver_name][flag] = driver_flag_counter[driver_name].get(flag, 0) + 1
                                            flag_counter[flag] = flag_counter.get(flag, 0) + 1

                            # Add the race if a match was found
                            if include_race or not filter_text:
                                if only_unfinished and not at_least_one_unfinished:
                                    continue
                                driver_counter[0] += 1
                                all_found_entries.append((race_number, race_details, race_entries, race_name))
                                print(f"Added to results: {race_number}, {race_details}")

                await asyncio.sleep(delay_time)  # Delay to avoid server overload
                break  # Exit retry loop if successful
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay_time * (2 ** attempt))  # Exponential backoff
                    continue
                result_text.insert(tk.END, f"Error fetching data from {url}: {e}\n")








import asyncio
import aiohttp

async def fetch_data_from_urls(selected_urls, filter_text, driver_counter, only_unfinished=False, selected_heat_types=None):
    global max_concurrent_requests, delay_time  # Use global settings

    # Justera antalet samtidiga förfrågningar baserat på antalet valda URL:er
    num_urls = len(selected_urls)
    if num_urls > 5:  # Om fler än 5 tävlingar är markerade, minska hastigheten
        max_concurrent_requests = 5  # Lägre samtidighet för att undvika överbelastning
        delay_time = 2.0  # Öka fördröjningen
    else:
        max_concurrent_requests = 10  # Snabbare för få tävlingar
        delay_time = 1.0  # Mindre fördröjning

    semaphore = asyncio.Semaphore(max_concurrent_requests)
    all_found_entries = []
    flag_counter = {}
    driver_flag_counter = {}
    failed_links = []

    async with aiohttp.ClientSession() as session:
        tasks = []

        for selected_url in selected_urls:
            links = await fetch_all_links(session, selected_url)
            race_name = next((key for key, value in link_dict.items() if value == selected_url), None)
            
            if not links:
                result_text.insert(tk.END, f"Inga giltiga länkar hittades för tävling: {selected_url}\n")
                continue

            for link in links:
                task = fetch_filtered_drivers(
                    session, link, filter_text, driver_counter, race_name,
                    only_unfinished, all_found_entries, [], selected_heat_types,
                    flag_counter, driver_flag_counter, semaphore, delay_time
                )
                tasks.append(task)

        # Kör alla förfrågningar och samla länkar som misslyckas
        progress["maximum"] = len(tasks)
        completed = 0

        if tasks:
            for task in asyncio.as_completed(tasks):
                try:
                    await task
                except Exception as e:
                    failed_links.append(task)
                completed += 1
                progress["value"] = completed
                root.update_idletasks()

        # Omhämta misslyckade länkar upp till 3 gånger
        retries = 3
        for attempt in range(retries):
            if not failed_links:
                break
            result_text.insert(tk.END, f"Försöker igen med {len(failed_links)} misslyckade länkar (försök {attempt + 1}/{retries})...\n")
            retry_tasks = failed_links
            failed_links = []
            for task in asyncio.as_completed(retry_tasks):
                try:
                    await task
                except Exception as e:
                    failed_links.append(task)

        # Bearbeta och visa data
        all_found_entries.sort(key=lambda x: x[0])
        positions = []

        if all_found_entries:
            flag_frame, flag_text, toggle_button = create_flag_summary_frame(result_text)

            if filter_text:
                filter_text_lower = filter_text.lower()  # Lägg till denna rad om den saknas

                specific_driver_flags = driver_flag_counter.get(filter_text_lower, None)
                if specific_driver_flags:
                    display_flag_summary(flag_text, specific_driver_flags, show_all_flags=True)
                else:
                    flag_text.insert(tk.END, f"Inga flaggor hittades för '{filter_text}'.\n")
            else:
                display_flag_summary(flag_text, flag_counter, show_all_flags=True)
                display_top_driver_statistics(flag_text, driver_flag_counter)

            display_race_results(all_found_entries, filter_text, result_text, positions)

        if positions and not auto_upload_enabled and show_trend_graph.get():
            root.after(0, lambda: show_position_graph(positions, driver_counter[0]))
        else:
            result_text.insert(tk.END, f" '{filter_text}'.\n")








def create_flag_summary_frame(parent):
    global flag_text  # Gör flag_text global för åtkomst i andra funktioner
    flag_frame = tk.Frame(root, relief=tk.RAISED, borderwidth=1)

    flag_scrollbar = tk.Scrollbar(flag_frame, orient=tk.VERTICAL)
    flag_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Justera höjd och bredd här för flag_text
    flag_text = tk.Text(flag_frame, wrap=tk.WORD, yscrollcommand=flag_scrollbar.set, height=25, width=120)
    flag_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    flag_scrollbar.config(command=flag_text.yview)

    toggle_button = tk.Button(
        parent, text="Näytä lippuyhteenveto", command=lambda: toggle_flag_summary(flag_frame, toggle_button)
    )
    toggle_button.place(relx=1.0, rely=0.0, anchor="ne")

    return flag_frame, flag_text, toggle_button

def toggle_flag_summary(flag_frame, toggle_button):
    """Visar eller döljer flaggsammanfattningsramen utan att ändra layouten på result_frame."""
    if flag_frame.winfo_ismapped():
        flag_frame.grid_remove()
        toggle_button.config(text="Näytä lippuyhteenveto")
    else:
        flag_frame.grid(row=5, column=0, columnspan=3, sticky="nsew", padx=10, pady=10)
        toggle_button.config(text="Piilota lippuyhteenveto")




def display_flag_summary(flag_text, flag_data, show_all_flags=False):
    """Visar flaggsammanfattning i textwidgeten, visar alla flaggtyper om show_all_flags är True."""
    if show_all_flags:
        # Samla alla möjliga flaggor som kan finnas och sätt till 0 om de saknas
        all_flags = ['M', 'MV', 'N', 'K', 'S']  # Lägg till fler flaggtyper om nödvändigt
        for flag in all_flags:
            if flag not in flag_data:
                flag_data[flag] = 0
    
    # Sammanfatta flaggorna och visa i textwidgeten
    flag_summary = "Liput yhteensä: " + " | ".join([f"{flag}: {count}" for flag, count in flag_data.items() if count > 0])
    print(f"Displaying flag summary: {flag_summary}")  # Log för att kontrollera flaggsammanfattningen
    flag_text.insert(tk.END, flag_summary + "\n\n")



def display_top_driver_statistics(flag_text, driver_flag_counter):
    """Visar toppstatistik för förare."""
    top_10_m_summary, top_10_mv_summary, top_5_n_summary, top_5_k_summary, top_5_starts_summary = get_driver_statistics(driver_flag_counter)
    print(f"Top driver statistics being displayed.")  # Log to confirm display of top driver statistics

    combined_summary = "{:<50} {:<50}\n".format("Top 10 kuljettajat lipuilla (M):", "Top 10 kuljettajat lipuilla (MV):")
    flag_text.insert(tk.END, combined_summary + "\n")

    for i in range(10):
        m_line = top_10_m_summary[i] if i < len(top_10_m_summary) else ""
        mv_line = top_10_mv_summary[i] if i < len(top_10_mv_summary) else ""
        combined_line = "{:<50} {:<50}\n".format(m_line, mv_line)
        flag_text.insert(tk.END, combined_line)

    flag_text.insert(tk.END, "\n")
    combined_summary_n_k_starts = "{:<50} {:<50}\n".format("Top 5 kuljettajat lipuilla (N):", "Top 5 kuljettajat lipuilla (K):")
    flag_text.insert(tk.END, combined_summary_n_k_starts + "\n")

    for i in range(5):
        n_line = top_5_n_summary[i] if i < len(top_5_n_summary) else ""
        k_line = top_5_k_summary[i] if i < len(top_5_k_summary) else ""
        combined_line_n_k = "{:<50} {:<50}\n".format(n_line, k_line)
        flag_text.insert(tk.END, combined_line_n_k)

    flag_text.insert(tk.END, "\nTop 5 kuljettajat startit:\n")
    for starts_line in top_5_starts_summary[:5]:
        flag_text.insert(tk.END, f"{starts_line}\n")
    flag_text.insert(tk.END, "\n")


def display_race_results(all_found_entries, filter_text, result_text, positions):
    """Visar tävlingsresultat och markerar sökningar i textwidgeten."""
    if all_found_entries:
        # Visa banans namn högst upp med "Kilpailu:" framför
        first_race_name = all_found_entries[0][3]  # Tar race_name från den första posten
        result_text.insert(tk.END, f"Lähdöt: {first_race_name}\n")

    # Skapa versioner av filter_text för att matcha både "förnamn efternamn" och "efternamn förnamn"
    parts = filter_text.split()
    if len(parts) == 2:
        name_versions = [filter_text, f"{parts[1]} {parts[0]}"]
    else:
        name_versions = [filter_text]

    for race_number, race_details, entries, race_name in all_found_entries:
        # Visa tävlingsnamnet innan varje heat på finska
        result_text.insert(tk.END, f"Kilpailun nimi: {race_name}\n", "race_name")
        
        # Ta bort strecken under tävlingsnamnet
        # result_text.insert(tk.END, "-" * 120 + "\n")
        
        result_text.insert(tk.END, f"{race_details}\n")
        for entry in entries:
            formatted_entry = (
                f"{entry[0]:<5}"
                f"{entry[1]:<5}"
                f"{entry[2]:<25}"
                f"{entry[3]:<25}"
                f"{entry[4]:<30}"
                f"{entry[5]:<15}"
            )

            # Kontrollera om något av namnen i name_versions finns i entry
            if any(re.fullmatch(re.escape(name), entry[2], re.IGNORECASE) for name in name_versions):
                result_text.insert(tk.END, formatted_entry + "\n", "highlight")
                try:
                    position_str = entry[5]
                    match = re.search(r'\d+', position_str)
                    position = int(match.group()) if match else None
                    positions.append(position)
                except ValueError:
                    positions.append(None)
            else:
                result_text.insert(tk.END, formatted_entry + "\n")
        
        # Infoga ett streck efter varje heat
        result_text.insert(tk.END, "-" * 120 + "\n")







def get_driver_statistics(driver_flag_counter):
    """Returnerar statistik för topp 10 och topp 5 förare för olika flaggtyper."""
    m_counts = {driver: flags.get("M", 0) for driver, flags in driver_flag_counter.items()}
    mv_counts = {driver: flags.get("MV", 0) for driver, flags in driver_flag_counter.items()}
    n_counts = {driver: flags.get("N", 0) for driver, flags in driver_flag_counter.items()}
    k_counts = {driver: flags.get("K", 0) for driver, flags in driver_flag_counter.items()}
    # Uteslut tomma förarnamn och "Kuljettaja"
    start_counts = {driver: flags.get("starts", 0) for driver, flags in driver_flag_counter.items() if driver.strip() and driver.lower() != "kuljettaja"}

    top_10_m_drivers = sorted(m_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    top_10_mv_drivers = sorted(mv_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    top_5_n_drivers = sorted(n_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_5_k_drivers = sorted(k_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_5_starts_drivers = sorted(start_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    top_10_m_summary = [f"{driver.title()}: {count} M-lippua ({driver_flag_counter[driver]['starts']} starttia)" for driver, count in top_10_m_drivers]
    top_10_mv_summary = [f"{driver.title()}: {count} MV-lippua ({driver_flag_counter[driver]['starts']} starttia)" for driver, count in top_10_mv_drivers]
    top_5_n_summary = [f"{driver.title()}: {count} N-lippua ({driver_flag_counter[driver]['starts']} starttia)" for driver, count in top_5_n_drivers]
    top_5_k_summary = [f"{driver.title()}: {count} K-lippua ({driver_flag_counter[driver]['starts']} starttia)" for driver, count in top_5_k_drivers]
    top_5_starts_summary = [f"{driver.title()}: {count} starttia" for driver, count in top_5_starts_drivers]

    return top_10_m_summary, top_10_mv_summary, top_5_n_summary, top_5_k_summary, top_5_starts_summary























# Function to safely show the position graph in the main thread
def show_position_graph(positions, total_starts):
    # Skapa en ny figur
    plt.figure(figsize=(10, 5))

    # Separera positioner med data från de utan data (saknade positioner)
    x_vals = range(1, len(positions) + 1)
    valid_positions = [pos for pos in positions if pos is not None]
    valid_x = [x_vals[i] for i, pos in enumerate(positions) if pos is not None]
    missing_x = [x_vals[i] for i, pos in enumerate(positions) if pos is None]

    # Plotta giltiga positioner
    plt.plot(valid_x, valid_positions, marker='o', linestyle='-', color='b', label='Sijoitus')

    # Plotta saknade positioner med röda punkter
    if missing_x:
        missing_y = [max(valid_positions) + 1] * len(missing_x)
        plt.scatter(missing_x, missing_y, color='r', marker='o', label='Ei tuloksia')

    # Detaljer för grafen
    plt.xlabel('Lähtö (Start)')
    plt.ylabel('Sijoitus (Position)')
    plt.title(f'Kuljettajan Sijoitus Jokaisessa Lähdössä (Yhteensä {total_starts} lähtöä)')
    plt.gca().invert_yaxis()  # Lägre värden är bättre positioner, så invertera y-axeln
    plt.grid(True)
    plt.legend()

    # Se till att grafen visas längst fram
    plt_window = plt.get_current_fig_manager().window
    plt_window.attributes('-topmost', 1)  # Sätt fönstret längst fram
    plt_window.attributes('-topmost', 0)  # Ta bort "topmost" efter att den kommit fram

    plt.show()



def start_scraping():
    threading.Thread(target=on_submit, daemon=True).start()

def on_submit():
    global selected_items_global

    # Spara de aktuellt markerade tävlingarna (baserat på tävlingarnas text)
    selected_items_global = [dropdown_menu.get(i) for i in dropdown_menu.curselection()]

    # Hämta de URL:er som är markerade för sökning
    selected_urls = [link_dict[item] for item in selected_items_global]
    filter_text = filter_entry.get().strip().lower()

    # Hämta valda heat-typer från checkboxar
    selected_heat_types = get_selected_heat_types()

    # Sätt progressbar till noll
    progress["value"] = 0
    progress["maximum"] = 100  # Set an initial value to give the bar a starting point

    # Uppdatera progressbaren för att visa att processen har startat
    root.update_idletasks()

    # Spara den aktuella scrollpositionen
    scroll_position = result_text.yview()

    # Rensa befintliga resultat i result_text Text widget
    result_text.delete(1.0, tk.END)
    # Rensa flaggsammanfattningen
    clear_flag_summary()

    # Lägg till plats för antalet resultat
    result_text.insert(tk.END, f"Kilpailu '{filter_text}': ...\n\n")

    # Återskapa headers
    result_text.insert(tk.END, "Rata  Nro  Kuljettaja                 Seura                   Auto                          Sijoitus+liput\n")
    result_text.insert(tk.END, "-" * 120 + "\n")

    driver_counter = [0]
    positions = []  # Lägg till positionslistan här

    # Uppdatera progressbaren för att visa att den går vidare till att hämta data
    progress["value"] = 10  # Set an early progress value
    root.update_idletasks()

    # Starta tidtagning
    start_time = time.time()

    def run_async_task_in_thread():
        nonlocal driver_counter, positions

        async def run_async_task():
            try:
                await fetch_data_from_urls(selected_urls, filter_text, driver_counter, only_unfinished, selected_heat_types)
            except Exception as e:
                result_text.insert(tk.END, f"Virhe tietojen käsittelyssä: {str(e)}\n")

        # Kör den asynkrona funktionen
        asyncio.run(run_async_task())

        # När det är klart, uppdatera UI i huvudtråden
        root.after(0, lambda: on_task_complete(driver_counter, start_time, filter_text, scroll_position, positions))

    # Kör asynkron uppgift i en bakgrundstråd
    threading.Thread(target=run_async_task_in_thread, daemon=True).start()






def on_task_complete(driver_counter, start_time, filter_text, scroll_position, positions):
    # Sluta tidtagning
    end_time = time.time()
    elapsed_time = end_time - start_time

    # Uppdatera progressbaren efter datainhämtning
    progress["value"] = 90
    root.update_idletasks()

    # Gå tillbaka och uppdatera antalet resultat på rätt plats
    result_text.delete("1.0", "2.0")
    result_text.insert("1.0", f"Kilpailu: {driver_counter[0]}\n")
    result_text.insert("2.0", f"Haku valmis. Aikaa kului: {elapsed_time:.2f} sekuntia.\n\n")

    # Debug print for positions
    print("Positions data before showing graph:", positions)

    # Återställ scrollpositionen efter uppdateringen
    result_text.yview_moveto(scroll_position[0])

    # Återställ de markerade tävlingarna efter sökningen är klar
    restore_selections()

    # Markera alla förekomster av användarens namn med en specifik bakgrundsfärg på hela raden
    if filter_text:
        highlight_name(filter_text)

    # Uppdatera progressbaren till fullständigt slutförd
    progress["value"] = 100
    root.update_idletasks()

    # Visa trendgrafen om alternativet är markerat
    if show_trend_graph.get() and positions:
        print("Checkbox is checked. Displaying trend graph...")
        show_position_graph(positions, driver_counter[0])
        print("Displaying the plot with plt.show()")
        plt.show()  # Wait for the user to close the plot before proceeding

    # Definiera en funktion för att nollställa progressbaren
    def reset_progress():
        progress["value"] = 0

    # Vänta lite innan progressbaren nollställs (ger användaren en visuell bekräftelse)
    root.after(500, reset_progress)








def restore_selections():
    dropdown_menu.selection_clear(0, tk.END)  # Ta bort alla tidigare markeringar
    for item in selected_items_global:
        index = dropdown_menu.get(0, tk.END).index(item)
        dropdown_menu.selection_set(index)

def highlight_name(name):
    # Ta bort alla tidigare markeringar innan en ny sökning utförs
    result_text.tag_remove("highlight", "1.0", tk.END)

    # Skapa två versioner av sökordet: 'förnamn efternamn' och 'efternamn förnamn'
    parts = name.split()
    if len(parts) == 2:
        name_versions = [name, f"{parts[1]} {parts[0]}"]
    else:
        name_versions = [name]

    # Skapa en ny tagg för att markera raden med grön bakgrund
    result_text.tag_configure("highlight", background="lightgreen")

    for version in name_versions:
        print(f"Söker efter: {version}")  # Debug-utskrift
        start_pos = "1.0"
        while True:
            start_pos = result_text.search(version, start_pos, stopindex=tk.END, nocase=True)
            if not start_pos:
                break

            # Hämta hela raden och kontrollera att den innehåller söktermen innan den markeras
            line_start = f"{start_pos.split('.')[0]}.0"
            line_end = f"{start_pos.split('.')[0]}.end"
            line_content = result_text.get(line_start, line_end).strip()

            # Kontrollera att raden innehåller söktermen
            if version.lower() in line_content.lower():
                print(f"Markerar rad: '{line_content}' vid position: {line_start} till {line_end}")
                result_text.tag_add("highlight", line_start, line_end)
            
            start_pos = f"{line_end}+1c"



def on_reset():
    global upload_task
    global auto_upload_enabled
    global only_unfinished

    dropdown_menu.selection_clear(0, tk.END)
    filter_entry.delete(0, tk.END)
    # Rensa result_text
    result_text.delete(1.0, tk.END)
    # Rensa flaggsammanfattningen
    clear_flag_summary()

    if upload_task:
        root.after_cancel(upload_task)
        upload_task = None
        auto_upload_enabled = False
        status_label.config(text="Automaattiset päivitykset ovat poissa käytöstä", fg="red")
        auto_upload_button.config(text="Aloita Automaattinen Päivitys")
    
    only_unfinished = False
    filter_unfinished_button.config(bg="red", text="Näytä Vain Keskeneräiset")


def on_filter_entry_change(event):
    selected_indices = dropdown_menu.curselection()
    if selected_indices:
        dropdown_menu.selection_clear(0, tk.END)
        for index in selected_indices:
            dropdown_menu.selection_set(index)

def on_arrow_key(event):
    if event.keysym == 'Up':
        dropdown_menu.select_set(dropdown_menu.curselection()[0] - 1)
        dropdown_menu.yview_scroll(-1, 'units')
    elif event.keysym == 'Down':
        dropdown_menu.select_set(dropdown_menu.curselection()[0] + 1)
        dropdown_menu.yview_scroll(1, 'units')



def print_results():
    # Ask for confirmation in Finnish
    confirm_print = messagebox.askyesno("Vahvista tulostus", "Haluatko varmasti tulostaa tulokset?")

    if confirm_print:
        # Get the content of the results window
        results_content = result_text.get(1.0, tk.END)
        
        # Use the default printer
        printer_name = win32print.GetDefaultPrinter()
        
        # Create a temporary file to send to the printer
        with open("results.txt", "w") as temp_file:
            temp_file.write(results_content)
        
        # Send the file to the printer
        win32api.ShellExecute(
            0,
            "print",
            "results.txt",
            f'/d:"{printer_name}"',
            ".",
            0
        )

def save_results_as():
    file_path = filedialog.asksaveasfilename(defaultextension=".txt",
                                             filetypes=[("Tekstitiedostot", "*.txt"),
                                                        ("Excel-tiedostot", "*.xlsx"),
                                                        ("HTML-tiedostot", "*.html")])
    if not file_path:
        return  # User canceled the save dialog

    try:
        if file_path.endswith(".txt"):
            with open(file_path, "w") as f:
                f.write(result_text.get(1.0, tk.END))
        elif file_path.endswith(".xlsx") or file_path.endswith(".html"):
            # Extract content from the Text widget, preserving format
            lines = result_text.get(1.0, tk.END).strip().splitlines()
            
            # Extract headers and data preserving the original layout
            header = ["Rata", "Nro", "Kuljettaja", "Seura", "Auto", "Sijoitus+liput"]
            data = []
            current_race_details = ""

            for line in lines:
                if line.startswith("Lähtö n:o"):  # Capture race details
                    current_race_details = line.strip()
                    data.append([current_race_details, "", "", "", "", "", ""])
                elif line.strip() == "-" * 120:  # Skip separator lines
                    continue
                elif line.strip():  # Skip empty lines
                    # Each line represents a row of data in the race table
                    split_line = [
                        line[0:5].strip(),  # Rata
                        line[5:10].strip(),  # Nro
                        line[10:35].strip(),  # Kuljettaja
                        line[35:60].strip(),  # Seura
                        line[60:90].strip(),  # Auto
                        line[90:105].strip(),  # Sijoitus+liput
                    ]
                    data.append(split_line)

            # Convert to DataFrame
            df = pd.DataFrame(data, columns=["Lähtö"] + header)

            if file_path.endswith(".xlsx"):
                df.to_excel(file_path, index=False)
            else:
                df.to_html(file_path, index=False, escape=False)
                
        messagebox.showinfo("Onnistui", f"Tiedosto tallennettiin onnistuneesti sijaintiin {file_path}")
    except Exception as e:
        messagebox.showerror("Virhe", f"Tiedoston tallennus epäonnistui: {e}")

def toggle_auto_upload():
    global auto_upload_enabled
    global upload_task
    
    if auto_upload_enabled:
        # Disable auto-upload
        if upload_task:
            root.after_cancel(upload_task)
            upload_task = None
        auto_upload_enabled = False
        status_label.config(text="Automaattiset päivitykset ovat poissa käytöstä", fg="red")
        auto_upload_button.config(text="Aloita Automaattinen Päivitys")
    else:
        # Enable auto-upload
        if len(dropdown_menu.curselection()) == 1:
            auto_upload_enabled = True
            status_label.config(text=f"Automaattiset päivitykset ovat käytössä (päivittyy {upload_interval // 1000} sekunnin välein)", fg="green")
            auto_upload_button.config(text="Lopeta Automaattinen Päivitys")
            upload_results_periodically()
        else:
            messagebox.showwarning("Varoitus", "Automaattinen päivitys toimii vain, kun yksi kilpailu on valittuna.")

def upload_results_periodically():
    if auto_upload_enabled:
        on_submit()  # Refresh results with the current filter setting
        global upload_task
        upload_task = root.after(upload_interval, upload_results_periodically)  # Run this function again after the set interval

def update_interval(val):
    global upload_interval
    upload_interval = int(val) * 1000
    if auto_upload_enabled:
        toggle_auto_upload()  # Turn it off
        toggle_auto_upload()  # Turn it back on with new interval

def toggle_unfinished_filter():
    global only_unfinished
    only_unfinished = not only_unfinished  # Toggle the state
    if only_unfinished:
        filter_unfinished_button.config(bg="green", text="Näytä Kaikki Lähdöt")
    else:
        filter_unfinished_button.config(bg="red", text="Näytä Vain Keskeneräiset")
    on_submit()

def show_about():
    about_window = tk.Toplevel(root)
    about_window.title("Tietoa")

    # Set the window size
    about_window.geometry("300x150")

    # Add the author name and website link
    about_label = tk.Label(about_window, text="Ohjelman tekijä: John Eveli", font=("Arial", 12))
    about_label.pack(pady=10)

    def open_website(event):
        webbrowser.open_new("http://johneveli.net")

    website_label = tk.Label(about_window, text="Vieraile johneveli.net", fg="blue", cursor="hand2", font=("Arial", 12, "underline"))
    website_label.pack()
    website_label.bind("<Button-1>", open_website)

    # Add a close button
    close_button = tk.Button(about_window, text="Sulje", command=about_window.destroy)
    close_button.pack(pady=10)







def show_how_to_use():
    instructions_fi = """
    SUOMI INSTRUKTIOT:

    JM Race Hub käyttö:

    1. Valitse kilpailu vasemmalla olevasta listasta.
    2. Voit suodattaa tuloksia syöttämällä kuljettajan tai seuran nimen suodatinkenttään.
    3. Napsauta "Hae" hakeaksesi tulokset. Ohjelma noutaa kaikki asiaankuuluvat lähdöt ja tulokset.
    4. Ohjelma näyttää liput ja startit kuljettajille. Liput yhteensä ja eri tyyppiset lähdöt esitetään.
    5. Jos valitset vain yhden kilpailun, voit ottaa automaattisen päivityksen käyttöön, joka päivittää tulokset valitun aikavälin mukaan.
    6. "Tallennus"-toiminnolla voit tallentaa tulokset tekstinä, Excel- tai HTML-tiedostona.
    7. "Näytä Vain Keskeneräiset" -painike suodattaa tulokset niin, että vain lähdöt ilman lopullista sijoitusta näkyvät.
    8. "Nollaa"-painike tyhjentää suodattimet, valitut kilpailut sekä palauttaa ohjelman alkuperäiseen tilaan.
    9. "Aloita Automaattinen Päivitys" -painikkeella voit käynnistää automaattisen päivityksen ja pysäyttää sen samalla painikkeella.
    10. Tulokset näytetään kolmessa eri sarakkeessa: liput (M, MV, K, N), startit, ja lähdöt, sekä lisäksi trendikaavio näyttää sijoituksen kehityksen.
    """

    instructions_sv = """
    SVENSKA INSTRUKTIONER:

    Användarinstruktioner för JM Race Hub:

    1. Välj en tävling från listan till vänster.
    2. Du kan filtrera resultaten genom att skriva in förarens eller klubbens namn i filtreringsfältet.
    3. Klicka på "Hämta" för att söka efter resultaten. Programmet hämtar alla relevanta heat och resultat.
    4. Programmet visar flaggor och starter för förarna. Flaggor totalt och olika heattyper visas.
    5. Om du endast väljer en tävling kan du aktivera automatisk uppdatering, som uppdaterar resultaten med den valda intervallen.
    6. Du kan spara resultaten som textfil, Excel-fil eller HTML-fil med "Spara"-funktionen.
    7. "Visa Endast Oavslutade"-knappen filtrerar resultaten så att endast de heat utan slutlig placering visas.
    8. "Återställ"-knappen rensar filter, valda tävlingar och återställer programmet till ursprungsläge.
    9. "Starta Automatisk Uppdatering"-knappen startar automatisk uppdatering, som du kan stoppa med samma knapp.
    10. Resultaten visas i tre olika kolumner: flaggor (M, MV, K, N), starter, och heat, samt en trendgraf som visar utvecklingen av placeringar.
    """

    # Create the "Användarinstruktioner / Käyttöohjeet" window
    how_to_window = tk.Toplevel(root)
    how_to_window.title("Användarinstruktioner / Käyttöohjeet")

    # Calculate 70% of the screen width and height
    screen_width = how_to_window.winfo_screenwidth()
    screen_height = how_to_window.winfo_screenheight()
    window_width = int(screen_width * 0.7)
    window_height = int(screen_height * 0.7)
    
    # Create the main frame
    main_frame = tk.Frame(how_to_window, padx=20, pady=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Create a Label for Finnish instructions
    fi_label = tk.Label(main_frame, text="SUOMI INSTRUKTIOT", font=("Arial", 14, "bold"), anchor="w")
    fi_label.pack(fill=tk.X)

    # Create a Text widget with a scrollbar for Finnish instructions
    instructions_text_fi = tk.Text(main_frame, wrap=tk.WORD, height=12, padx=10, pady=10, font=("Arial", 10))
    instructions_text_fi.insert(tk.END, instructions_fi)
    instructions_text_fi.config(state=tk.DISABLED)  # Make the text read-only
    instructions_text_fi.pack(fill=tk.BOTH, expand=True)

    scrollbar_fi = tk.Scrollbar(instructions_text_fi, command=instructions_text_fi.yview)
    instructions_text_fi.config(yscrollcommand=scrollbar_fi.set)
    scrollbar_fi.pack(side=tk.RIGHT, fill=tk.Y)

    # Create a Label for Swedish instructions
    sv_label = tk.Label(main_frame, text="SVENSKA INSTRUKTIONER", font=("Arial", 14, "bold"), anchor="w")
    sv_label.pack(fill=tk.X, pady=(10, 0))

    # Create a Text widget with a scrollbar for Swedish instructions
    instructions_text_sv = tk.Text(main_frame, wrap=tk.WORD, height=12, padx=10, pady=10, font=("Arial", 10))
    instructions_text_sv.insert(tk.END, instructions_sv)
    instructions_text_sv.config(state=tk.DISABLED)  # Make the text read-only
    instructions_text_sv.pack(fill=tk.BOTH, expand=True)

    scrollbar_sv = tk.Scrollbar(instructions_text_sv, command=instructions_text_sv.yview)
    instructions_text_sv.config(yscrollcommand=scrollbar_sv.set)
    scrollbar_sv.pack(side=tk.RIGHT, fill=tk.Y)

    # Add a close button at the bottom
    close_button = tk.Button(main_frame, text="Stäng / Sulje", command=how_to_window.destroy, font=("Arial", 12))
    close_button.pack(pady=10, side=tk.BOTTOM)

    # Set the window size to 70% of the screen size
    how_to_window.geometry(f"{window_width}x{window_height}")

    # Center the window on the screen
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2
    how_to_window.geometry(f"+{x}+{y}")

    # Ensure the window is resizable
    how_to_window.resizable(True, True)

root = tk.Tk()
root.title("JM Race Hub")

# Create show_trend_graph after root window is initialized
show_trend_graph = tk.BooleanVar(value=False)

# Set icon for the application
try:
    root.iconbitmap(ico_path)
except Exception as e:
    print(f"Icon not found: {e}")

instruction_label = tk.Label(
    root, 
    text="Jos haluat hakea tietyn kuljettajan, kirjoita ensin nimi, valitse sitten kilpailu ja rastita 'Näytä trendikaavio', jos haluat nähdä tulosten trendit.", 
    fg="red"
)
instruction_label.grid(row=0, column=0, columnspan=3, pady=5, padx=5)


links = asyncio.run(fetch_main_page_links())
link_dict = {text: url for text, url, date in links}

# Create the main frame
main_frame = tk.Frame(root)
main_frame.grid(row=1, column=0, columnspan=3, sticky="nsew")

# Create a PanedWindow for resizable panels
paned_window = tk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
paned_window.pack(fill=tk.BOTH, expand=True)

# Create a frame for the dropdown menu with a scrollbar
dropdown_frame = tk.Frame(paned_window)
paned_window.add(dropdown_frame)

dropdown_menu = tk.Listbox(dropdown_frame, selectmode="extended", width=40, height=30)
for text in link_dict.keys():
    dropdown_menu.insert(tk.END, text)  # Ensure this correctly populates the listbox
dropdown_menu.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

scrollbar = tk.Scrollbar(dropdown_frame, orient=tk.VERTICAL)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
dropdown_menu.config(yscrollcommand=scrollbar.set)
scrollbar.config(command=dropdown_menu.yview)

# Bind arrow keys to the dropdown menu
dropdown_menu.bind("<Up>", on_arrow_key)
dropdown_menu.bind("<Down>", on_arrow_key)

# Create a frame for the results with a scrollbar
result_frame = tk.Frame(paned_window)
paned_window.add(result_frame, stretch="always")

result_text = tk.Text(result_frame, wrap=tk.WORD, height=20, width=80, font=result_font)
result_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

result_scrollbar = tk.Scrollbar(result_frame, orient=tk.VERTICAL)
result_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
result_text.config(yscrollcommand=result_scrollbar.set)
result_scrollbar.config(command=result_text.yview)

# Create filter frame
filter_frame = tk.Frame(root)
filter_frame.grid(row=2, column=0, columnspan=3, sticky="ew")
tk.Label(filter_frame, text="Syötä kuljettajan nimi suodatusta varten:").pack(side=tk.LEFT, padx=5)



# Add checkboxes for filtering heat types
heat_types = ["Alkuerä", "Keräilyerä", "Välierä", "Semifinaali", "Sijoituserä", "Finaali"]
heat_vars = {}

for heat in heat_types:
    heat_vars[heat] = tk.BooleanVar(value=False)
    tk.Checkbutton(filter_frame, text=heat, variable=heat_vars[heat]).pack(side=tk.LEFT, padx=5)

# Add a function to extract selected heat types
def get_selected_heat_types():
    return [heat for heat, var in heat_vars.items() if var.get()]




# Driver name filter entry
filter_entry = tk.Entry(filter_frame, width=30)
filter_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

filter_entry.bind("<KeyRelease>", on_filter_entry_change)

# Create button frame
button_frame = tk.Frame(root)
button_frame.grid(row=3, column=0, columnspan=3, sticky="ew")
submit_button = tk.Button(button_frame, text="Hae", command=start_scraping)
submit_button.pack(side=tk.LEFT, padx=5, pady=5)
reset_button = tk.Button(button_frame, text="Nollaa", command=on_reset)
reset_button.pack(side=tk.LEFT, padx=5, pady=5)
save_button = tk.Button(button_frame, text="Tallenna tulokset", command=save_results_as)
save_button.pack(side=tk.LEFT, padx=5, pady=5)
auto_upload_button = tk.Button(button_frame, text="Aloita Automaattinen Päivitys", command=toggle_auto_upload)
auto_upload_button.pack(side=tk.LEFT, padx=5, pady=5)

# Add checkbox for trend graph
tk.Checkbutton(button_frame, text="Näytä trendikaavio", variable=show_trend_graph).pack(side=tk.LEFT, padx=5, pady=5)

# Lägg till en progressbar i GUI:t
progress = ttk.Progressbar(button_frame, orient="horizontal", length=400, mode="determinate")
progress.pack(side=tk.LEFT, padx=5, pady=5)

# Add a scale to adjust the auto-upload interval
interval_scale = tk.Scale(button_frame, from_=10, to=120, orient=tk.HORIZONTAL,
                          label="Päivitysväli (s)", command=update_interval)
interval_scale.set(upload_interval // 1000)  # Set initial value to match the default interval
interval_scale.pack(side=tk.LEFT, padx=5, pady=5)

# Add a scale to adjust the font size of the results
font_scale = tk.Scale(button_frame, from_=3, to=20, orient=tk.HORIZONTAL,
                      label="Tekstin koko", command=update_font_size)
font_scale.set(current_font_size)  # Set initial value to match the default font size
font_scale.pack(side=tk.LEFT, padx=5, pady=5)




# Add the "Print" button to the button frame
print_button = tk.Button(button_frame, text="Print", command=print_results)
print_button.pack(side=tk.LEFT, padx=5, pady=5)




# Move the "Näytä Vain Keskeneräiset" button to the filter frame
filter_unfinished_button = tk.Button(filter_frame, text="Näytä Vain Keskeneräiset", width=20, bg="red", command=toggle_unfinished_filter)
filter_unfinished_button.pack(side=tk.LEFT, padx=5, pady=5)

# Status bar to indicate automatic updates
status_frame = tk.Frame(root)
status_frame.grid(row=4, column=0, columnspan=3, sticky="ew")

status_label = tk.Label(status_frame, text="Automaattiset päivitykset ovat poissa käytöstä", fg="red", anchor="w")
status_label.pack(fill=tk.X, padx=5, pady=2)

# Add a menu bar
menu_bar = tk.Menu(root)
root.config(menu=menu_bar)

# Add the "Help" menu
help_menu = tk.Menu(menu_bar, tearoff=0)
menu_bar.add_cascade(label="Ohje", menu=help_menu)
help_menu.add_command(label="Käyttöohjeet", command=show_how_to_use)
help_menu.add_command(label="Tietoa", command=show_about)
# Function to handle enabling fastest mode from the menu
# Function to handle enabling and disabling fastest mode from the menu


# Initialize the fastest mode status
fastest_mode_enabled = False





# Add links to the menu bar
menu_bar.add_command(label="Jokkis Online", command=lambda: webbrowser.open_new("https://jokkis.net/online2/index.php"))
menu_bar.add_command(label="Kiti", command=lambda: webbrowser.open_new("https://akk.autourheilu.fi/Login.aspx?ReturnUrl=%2fKiti%2fMy%2fLicenses.aspx"))
menu_bar.add_command(label="Jokkiksen Kilpailukalenteri 2025", command=lambda: webbrowser.open_new("https://www.autourheilu.fi/kalenterit/kilpailukalenteri/jokamiehenluokka/"))

# Configure row and column weights to ensure proper resizing
root.grid_rowconfigure(1, weight=1)
root.grid_rowconfigure(2, weight=0)
root.grid_rowconfigure(3, weight=0)
root.grid_columnconfigure(0, weight=1)
root.grid_columnconfigure(1, weight=0)
root.grid_columnconfigure(2, weight=3)

main_frame.grid_rowconfigure(0, weight=1)
main_frame.grid_columnconfigure(0, weight=1)
main_frame.grid_columnconfigure(2, weight=3)
# Variabel för att spåra tangentsekvensen
key_sequence = []

def toggle_fastest_mode():
    global fastest_mode_enabled, max_concurrent_requests, delay_time

    if fastest_mode_enabled:
        # Avaktivera snabbfart och återgå till halvfart
        max_concurrent_requests = default_max_concurrent_requests
        delay_time = default_delay_time
        fastest_mode_enabled = False
        messagebox.showinfo("Nopein tila", "Nopein tila on pois päältä.")
    else:
        # Aktivera snabbfart
        max_concurrent_requests = 10  # Maximal samtidighet för snabbaste läge
        delay_time = 0.0  # Ingen fördröjning mellan förfrågningar
        fastest_mode_enabled = True
        messagebox.showinfo("Nopein tila", "Nopein tila on päällä.")

def check_fast_mode_activation(event):
    global key_sequence

    # Lägg till den tryckta tangenten till sekvensen
    key_sequence.append(event.keysym)

    # Kontrollera om sekvensen motsvarar 'Shift' + 'J', 'O', 'K', 'K', 'I', 'S'
    if key_sequence[-7:] == ['Shift_L', 'J', 'O', 'K', 'K', 'I', 'S']:
        toggle_fastest_mode()  # Aktivera eller avaktivera snabbfart
        key_sequence.clear()  # Återställ sekvensen efter aktivering
    elif len(key_sequence) > 7:
        # Begränsa sekvensens längd till de senaste 7 tangenttrycken
        key_sequence.pop(0)

# Bind tangenttryck för att lyssna efter sekvensen
root.bind("<Key>", check_fast_mode_activation)
root.minsize(800, 600)
root.mainloop()
