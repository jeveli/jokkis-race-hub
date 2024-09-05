import asyncio
import aiohttp
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# Globala variabler
only_unfinished = False  # Global flag to track if we should only show unfinished races

# Hämta huvudsidans länkar
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

async def fetch_filtered_drivers(session, url, filter_text, driver_counter, race_name, only_unfinished=False):
    try:
        async with session.get(url) as response:
            content = await response.text()
            soup = BeautifulSoup(content, "html.parser")
            
            race_elements = soup.find_all(string=lambda text: "Lähtö n:o" in text)
            found_entries = []

            filter_text_parts = filter_text.strip().split()
            filter_variants = [filter_text]

            if len(filter_text_parts) > 1:
                reversed_filter_text = " ".join(reversed(filter_text_parts))
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
                            driver_info = " ".join([col.text.strip() for col in columns])
                            race_entries.append([col.text.strip() for col in columns])

                            if columns[5].text.strip():
                                all_entries_unfinished = False
                            
                            driver_info_lower = driver_info.lower()
                            for variant in filter_variants:
                                if variant.lower() in driver_info_lower:
                                    include_race = True
                                    break
                    
                    if only_unfinished and not all_entries_unfinished:
                        continue

                    if include_race or (only_unfinished and all_entries_unfinished):
                        found_entries.append((race_number, race_details, race_entries))
                        driver_counter[0] += 1

            if found_entries:
                result_text = f"\n{race_name}\n"
                for race_number, race_details, entries in found_entries:
                    result_text += "-" * 120 + "\n"
                    result_text += f"{race_details}\n"
                    for entry in entries:
                        formatted_entry = (
                            f"{entry[0]:<5}"   
                            f"{entry[1]:<5}"   
                            f"{entry[2]:<25}"  
                            f"{entry[3]:<25}"  
                            f"{entry[4]:<30}"  
                            f"{entry[5]:<15}"  
                        )
                        result_text += formatted_entry + "\n"
                result_text += "\n"
                
                # Append or update result in session_state
                if "results" in st.session_state:
                    st.session_state.results += result_text
                else:
                    st.session_state.results = result_text
    except Exception as e:
        st.error(f"Virhe tietojen haussa {url}: {e}")

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

# Titel och instruktioner
st.title("Jokkis Race Hub")
st.write("Ange ett sökord och välj sedan tävlingar.")

# Justerbar uppdateringsintervall
upload_interval = st.slider("Välj uppdateringsintervall (sekunder)", min_value=5, max_value=120, value=20, step=5)

# Automatisk uppdatering
auto_update = st.checkbox("Aktivera automatisk uppdatering")
if auto_update:
    st_autorefresh(interval=upload_interval * 1000)  # Uppdaterar sidan baserat på användarens val

# Hämta länkar från huvudsidan
links = asyncio.run(fetch_main_page_links())
link_dict = {text: url for text, url, date in links}

# Dropdown för att välja tävlingar
selected_races = st.multiselect("Välj tävlingar", list(link_dict.keys()))

# Textinmatning för att filtrera efter förare eller klubb
filter_text = st.text_input("Skriv in klubbens eller förarens namn:")

# Alternativ för att endast visa pågående lopp
only_unfinished = st.checkbox("Visa endast oavslutade lopp")

# Knapp för att starta sökningen
if st.button("Hämta"):
    driver_counter = [0]
    selected_urls = [link_dict[race] for race in selected_races]
    asyncio.run(fetch_data_from_urls(selected_urls, filter_text, driver_counter, only_unfinished))
    st.write(f"Totalt antal heat för '{filter_text}': {driver_counter[0]}")

# Visa resultaten från session_state utan att de försvinner vid uppdatering
if "results" in st.session_state:
    st.text(st.session_state.results)
