import asyncio
import aiohttp
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# Enable wide view
st.set_page_config(layout="wide")

# Global variables
only_unfinished = False  # Global flag to track if we should only show unfinished races

# Language selection: Swedish or Finnish
lang = st.sidebar.selectbox("Välj språk / Valitse kieli", ["Svenska", "Suomi"])

# Instructions in both languages, collapsed by default
def show_instructions(language):
    if language == "Svenska":
        with st.sidebar.expander("Instruktioner", expanded=False):
            st.write("""
            1. Välj tävling från listan eller lämna tomt för att söka i alla tävlingar.
            2. Ange förarens eller klubbens namn i sökfältet.
            3. Tryck på "Hämta" för att visa resultaten.
            4. Om du vill uppdatera resultaten automatiskt, markera rutan för automatisk uppdatering.
            5. Du kan också filtrera pågående lopp genom att markera "Visa endast oavslutade lopp".
            6. Använd "Rensa allt" för att återställa resultaten och börja om.
            """)
    elif language == "Suomi":
        with st.sidebar.expander("Ohjeet", expanded=False):
            st.write("""
            1. Valitse kilpailu listasta tai jätä valitsematta, jolloin haetaan kaikista kilpailuista.
            2. Syötä kuljettajan tai seuran nimi hakukenttään.
            3. Paina "Hae" näyttääksesi tulokset.
            4. Jos haluat päivittää tulokset automaattisesti, merkitse ruutu automaattinen päivitys.
            5. Voit myös suodattaa keskeneräiset lähdöt valitsemalla "Näytä vain keskeneräiset lähdöt".
            6. Käytä "Tyhjennä kaikki" aloittaaksesi alusta.
            """)

# Display instructions in the sidebar (collapsed by default)
show_instructions(lang)

# Translations for titles, buttons, and labels
if lang == "Svenska":
    title = "Jokkis Race Hub"
    search_label = "Ange ett sökord och välj sedan tävlingar eller lämna tomt för att söka i alla tävlingar."
    fetch_button_label = "Hämta"
    clear_button_label = "Rensa allt"
    update_label = "Välj uppdateringsintervall (sekunder)"
    auto_update_label = "Aktivera automatisk uppdatering"
    show_unfinished_label = "Visa endast oavslutade lopp"
    search_placeholder = "Skriv in klubbens eller förarens namn:"
    total_heats_text = "Totalt antal heat för"
    cleared_text = "Resultaten har rensats. Uppdatera sidan för att börja om."
else:
    title = "Jokkis Kilpailu Hub"
    search_label = "Syötä hakusana ja valitse kilpailut tai jätä tyhjäksi, jolloin haetaan kaikista kilpailuista."
    fetch_button_label = "Hae"
    clear_button_label = "Tyhjennä kaikki"
    update_label = "Valitse päivitysväli (sekunteina)"
    auto_update_label = "Ota automaattinen päivitys käyttöön"
    show_unfinished_label = "Näytä vain keskeneräiset lähdöt"
    search_placeholder = "Kirjoita seuran tai kuljettajan nimi:"
    total_heats_text = "Lähtöjen kokonaismäärä"
    cleared_text = "Tulokset on tyhjennetty. Päivitä sivu aloittaaksesi alusta."

# Title and instructions
st.title(title)
st.write(search_label)

# Adjustable update interval
upload_interval = st.slider(update_label, min_value=5, max_value=120, value=20, step=5)

# Automatic update checkbox
auto_update = st.checkbox(auto_update_label)
if auto_update:
    st_autorefresh(interval=upload_interval * 1000)  # Auto-refreshes the page based on the user's interval choice

# Fetch links from the main page
async def fetch_main_page_links():
    url = "https://jokkis.net/online2/index.php"
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        st.error(f"Virhe päivitettäessä pääsivua: {e}")
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
        async with session.get(url) as response:
            content = await response.text()
            soup = BeautifulSoup(content, "html.parser")
            links = soup.find_all("a", href=True)

            valid_links = []
            for link in links:
                if "lahto_selailu.php" in link['href']:
                    full_url = requests.compat.urljoin(url, link['href'])
                    valid_links.append(full_url)

            return valid_links
    except Exception as e:
        st.error(f"Virhe päivitettäessä pääsivua: {e}")
        return []

# Get race links and store in link_dict
links = asyncio.run(fetch_main_page_links())
link_dict = {text: url for text, url, date in links}

# Extract race details
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

def extract_race_number(race_details):
    match = re.search(r'Lähtö n:o (\d+)', race_details)
    return int(match.group(1)) if match else None

# Fetch and filter driver data
async def fetch_filtered_drivers(session, url, filter_text, driver_counter, race_name, only_unfinished=False):
    try:
        async with session.get(url) as response:
            content = await response.text()
            soup = BeautifulSoup(content, "html.parser")
            
            race_elements = soup.find_all(string=lambda text: "Lähtö n:o" in text)
            found_entries = []

            filter_text_parts = filter_text.strip().split()
            filter_variants = [filter_text.lower()]

            if len(filter_text_parts) > 1:
                reversed_filter_text = " ".join(reversed(filter_text_parts)).lower()
                filter_variants.append(reversed_filter_text)

            for race_element in race_elements:
                race_details = extract_full_race_details(race_element)
                race_number = extract_race_number(race_details)
                race_table = race_element.find_next("table")
                
                if race_table:
                    rows = race_table.find_all("tr")
                    race_entries = []
                    include_race = False
                    all_entries_unfinished = True

                    for row in rows:
                        columns = row.find_all("td")
                        if len(columns) >= 6:
                            driver_info = " ".join([col.text.strip() for col in columns]).lower()
                            race_entries.append([col.text.strip() for col in columns])

                            if columns[5].text.strip():
                                all_entries_unfinished = False
                            
                            for variant in filter_variants:
                                if variant in driver_info:
                                    include_race = True
                                    break
                    
                    if only_unfinished and not all_entries_unfinished:
                        continue

                    if include_race:
                        found_entries.append((race_number, race_details, race_entries))
                        driver_counter[0] += 1

            if found_entries:
                result_text = f"\n{race_name}\n"
                for race_number, race_details, entries in found_entries:
                    result_text += "-" * 120 + "\n"
                    result_text += f"{race_details}\n"
                    for entry in entries:
                        formatted_entry = (
                            f"{entry[0]:<5}"   # Rata
                            f"{entry[1]:<5}"   # Nro
                            f"{entry[2]:<25}"  # Kuljettaja
                            f"{entry[3]:<25}"  # Seura
                            f"{entry[4]:<30}"  # Auto
                            f"{entry[5]:<15}"  # Sijoitus+liput
                        )
                        result_text += formatted_entry + "\n"
                result_text += "\n"
                
                # Add results to session state
                if "results" in st.session_state:
                    st.session_state.results += result_text
                else:
                    st.session_state.results = result_text
    except Exception as e:
        st.error(f"Virhe tietojen haussa {url}: {e}")

# Fetch race data
async def fetch_data_from_urls(selected_urls, filter_text, driver_counter, only_unfinished=False):
    async with aiohttp.ClientSession() as session:
        for selected_url in selected_urls:
            race_name = [key for key, value in link_dict.items() if value == selected_url][0]
            links = await fetch_all_links(session, selected_url)
            
            if links:
                tasks = [fetch_filtered_drivers(session, link, filter_text, driver_counter, race_name, only_unfinished) for link in links]
                await asyncio.gather(*tasks)
            else:
                st.write(f"Yhtään kelvollista linkkiä ei löytynyt pääsivulta: {selected_url}")

# Dropdown to select races
selected_races = st.multiselect("Välj tävlingar / Valitse kilpailut", list(link_dict.keys()))

# Input field for filtering by driver or club
filter_text = st.text_input(search_placeholder)

# Checkbox to show only unfinished races
only_unfinished = st.checkbox(show_unfinished_label)

# Two columns for buttons
col1, col2 = st.columns([1, 1])

with col1:
    # Fetch results button
    if st.button(fetch_button_label, key="fetch_button"):
        st.session_state.results = ""  # Clear previous results
        driver_counter = [0]
        # If no races selected, search all races
        if not selected_races:
            selected_urls = list(link_dict.values())  # Search all races
        else:
            selected_urls = [link_dict[race] for race in selected_races]
        
        asyncio.run(fetch_data_from_urls(selected_urls, filter_text, driver_counter, only_unfinished))
        st.write(f"{total_heats_text} '{filter_text}': {driver_counter[0]}")

with col2:
    # Clear results button
    if st.button(clear_button_label, key="clear_button"):
        if "results" in st.session_state:
            st.session_state.results = ""  # Clear results
        st.write(cleared_text)

# Display the results from session state
if "results" in st.session_state:
    st.text(st.session_state.results)
