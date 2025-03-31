import requests
import urllib.parse
import time
import asyncio
from bs4 import BeautifulSoup
from telegram import Bot
import os

# Amazon search URL for new movie releases
AMAZON_URL = "https://www.amazon.in/s?i=instant-video&rh=n%3A15457882031%2Cp_n_feature_three_browse-bin%3A15629640031%257C15629649031%257C15629664031%257C15629699031%257C15629700031&s=date-desc-rank"

# Headers to avoid bot detection
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}

#proxies

proxies= {
    "https://KeHNW228zLMx2DFwJ7jBCAmu:VRmxsZYEqskYbaFhbwqyy6A8@in-del.prod.surfshark.com:443",
    # "https://KeHNW228zLMx2DFwJ7jBCAmu:VRmxsZYEqskYbaFhbwqyy6A8@in-del.prod.surfshark.com:443",
}

# Keep track of already displayed movies
seen_movies = set()

# Telegram Bot Setup
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
bot = Bot(token=TELEGRAM_BOT_TOKEN)

async def send_telegram_message(text):
    """Send a message to the Telegram channel."""
    try:
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=text,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"Error sending message: {e}")

def fetch_amazon_page():
    """Fetch the Amazon movie page HTML."""
    response = requests.get(AMAZON_URL, headers=HEADERS, proxies=proxies)
    return response.text if response.status_code == 200 else None

def extract_movie_data(html):
    """Extract movie names, years, and redirect links from the Amazon page."""
    soup = BeautifulSoup(html, "html.parser")
    movies = []

    for h2_tag in soup.find_all("h2", class_="a-size-medium a-spacing-none a-color-base a-text-normal"):
        movie_name = h2_tag.text.strip()
        
        parent_a_tag = h2_tag.find_parent("a", class_="a-link-normal")
        if parent_a_tag and "href" in parent_a_tag.attrs:
            amazon_redirect_url = "https://www.amazon.in" + parent_a_tag["href"]
            
            year_span = h2_tag.find_next("span", class_="a-size-base a-color-secondary a-text-normal")
            movie_year = year_span.text.strip() if year_span else "Unknown"

            movies.append((movie_name, movie_year, amazon_redirect_url))

    return movies

def convert_to_prime_url(redirect_link):
    """Convert Amazon redirect link to Prime Video link."""
    parsed_url = urllib.parse.urlparse(redirect_link)
    query_params = urllib.parse.parse_qs(parsed_url.query)

    if "ru" in query_params:
        prime_link_encoded = query_params["ru"][0]
        prime_link = urllib.parse.unquote(prime_link_encoded)

        if "gti=" in prime_link:
            gti_value = prime_link.split("gti=")[-1].split("&")[0]
            return f"https://www.primevideo.com/detail/{gti_value}/"

    return None

def fetch_audio_languages(prime_video_url):
    """Extract available audio languages from the Prime Video page."""
    response = requests.get(prime_video_url, headers=HEADERS, proxies=proxies)
    if response.status_code != 200:
        return "Unknown"

    soup = BeautifulSoup(response.text, "html.parser")
    
    # Find all metadata rows
    metadata_rows = soup.find_all("dl", {"data-testid": "metadata-row"})

    for row in metadata_rows:
        dt_tag = row.find("dt")
        if dt_tag and "Audio languages" in dt_tag.text:
            dd_tag = row.find("dd")
            if dd_tag:
                return dd_tag.text.strip()

    return "Unknown"

async def main():
    """Main async function with proper event loop management."""
    global seen_movies

    while True:
        html = fetch_amazon_page()
        if not html:
            await asyncio.sleep(5)
            continue

        movies = extract_movie_data(html)
        new_movies = []

        for movie_name, movie_year, amazon_redirect in movies:
            prime_video_link = convert_to_prime_url(amazon_redirect)

            if prime_video_link:
                movie_key = f"{movie_name} ({movie_year})"
                
                if movie_key not in seen_movies:
                    seen_movies.add(movie_key)
                    audio_languages = fetch_audio_languages(prime_video_link)
                    new_movies.append((movie_name, movie_year, prime_video_link, audio_languages))
        
        if new_movies:
            for movie_name, movie_year, prime_video_link, audio_languages in new_movies:
                text = f"🎬 *New Movie:* {movie_name} ({movie_year})\n🔗 [Watch on Prime Video]({prime_video_link})\n🎧 *Audio:* {audio_languages}"
                print(text)
                await send_telegram_message(text)

        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
