import requests
import urllib.parse
import time
import asyncio
import logging
import aiohttp
from bs4 import BeautifulSoup
from telegram import Bot
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Set

# Configure logging to console only (no file handlers)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("PrimeVideoBot")

# Amazon search URL for new movie releases
AMAZON_URL = "https://www.amazon.in/s?i=instant-video&rh=n%3A15457882031%2Cp_n_feature_three_browse-bin%3A15629640031%257C15629649031%257C15629664031%257C15629699031%257C15629700031&s=date-desc-rank"

# Headers to avoid bot detection
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}

# Proxies
proxies = {
    "http": os.getenv("PROXY"),
    "https": os.getenv("PROXY"),
}

# Keep track of already displayed movies
seen_movies = set()

# Request state tracking (in-memory only)
request_states = {
    "amazon_page": {"status": "idle", "last_request": None, "success_count": 0, "error_count": 0},
    "prime_video": {"status": "idle", "last_request": None, "success_count": 0, "error_count": 0},
    "telegram": {"status": "idle", "last_request": None, "success_count": 0, "error_count": 0}
}

# Telegram Bot Setup
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

async def update_request_state(service: str, status: str, success: bool = True):
    """Update the request state for a service."""
    now = datetime.now().isoformat()
    request_states[service]["status"] = status
    request_states[service]["last_request"] = now
    
    if success:
        request_states[service]["success_count"] += 1
    else:
        request_states[service]["error_count"] += 1
    
    logger.info(f"Request state updated for {service}: {status} (success: {success})")

async def send_telegram_message(text: str) -> bool:
    """Send a message to the Telegram channel with state tracking."""
    try:
        await update_request_state("telegram", "sending")
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=text,
            parse_mode="Markdown",
            disable_web_page_preview=False
        )
        await update_request_state("telegram", "completed", True)
        return True
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        await update_request_state("telegram", "error", False)
        return False

async def fetch_amazon_page() -> Optional[str]:
    """Fetch the Amazon movie page HTML with state tracking and retries."""
    for attempt in range(MAX_RETRIES):
        try:
            await update_request_state("amazon_page", "fetching")
            async with aiohttp.ClientSession() as session:
                async with session.get(AMAZON_URL, headers=HEADERS, proxy=proxies.get("http")) as response:
                    if response.status == 200:
                        html = await response.text()
                        await update_request_state("amazon_page", "completed", True)
                        return html
                    else:
                        logger.warning(f"Amazon page request failed with status {response.status}")
                        await update_request_state("amazon_page", "error", False)
        except Exception as e:
            logger.error(f"Error fetching Amazon page (attempt {attempt+1}/{MAX_RETRIES}): {e}")
            await update_request_state("amazon_page", "error", False)
        
        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(RETRY_DELAY)
    
    return None

def extract_movie_data(html: str) -> List[Tuple[str, str, str]]:
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

    logger.info(f"Extracted {len(movies)} movies from Amazon page")
    return movies

def convert_to_prime_url(redirect_link: str) -> Optional[str]:
    """Convert Amazon redirect link to Prime Video link."""
    try:
        parsed_url = urllib.parse.urlparse(redirect_link)
        query_params = urllib.parse.parse_qs(parsed_url.query)

        if "ru" in query_params:
            prime_link_encoded = query_params["ru"][0]
            prime_link = urllib.parse.unquote(prime_link_encoded)

            if "gti=" in prime_link:
                gti_value = prime_link.split("gti=")[-1].split("&")[0]
                return f"https://www.primevideo.com/detail/{gti_value}/"
    except Exception as e:
        logger.error(f"Error converting to Prime URL: {e}")
    
    return None

async def fetch_audio_languages_and_poster(prime_video_url: str) -> Tuple[str, str]:
    """Extract available audio languages and poster image from the Prime Video page with state tracking."""
    for attempt in range(MAX_RETRIES):
        try:
            await update_request_state("prime_video", "fetching")
            async with aiohttp.ClientSession() as session:
                async with session.get(prime_video_url, headers=HEADERS, proxy=proxies.get("http")) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, "html.parser")
                        
                        # Find all metadata rows
                        metadata_rows = soup.find_all("dl", {"data-testid": "metadata-row"})
                        audio_languages = "Unknown"

                        for row in metadata_rows:
                            dt_tag = row.find("dt")
                            if dt_tag and "Audio languages" in dt_tag.text:
                                dd_tag = row.find("dd")
                                if dd_tag:
                                    audio_languages = dd_tag.text.strip()

                        # Extract movie poster
                        poster_tag = soup.find("meta", property="og:image")
                        poster_url = poster_tag["content"] if poster_tag else "Unknown"

                        await update_request_state("prime_video", "completed", True)
                        return audio_languages, poster_url
                    else:
                        logger.warning(f"Prime Video page request failed with status {response.status}")
                        await update_request_state("prime_video", "error", False)
        except Exception as e:
            logger.error(f"Error fetching Prime Video page (attempt {attempt+1}/{MAX_RETRIES}): {e}")
            await update_request_state("prime_video", "error", False)
        
        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(RETRY_DELAY)
    
    return "Unknown", "Unknown"

async def print_request_states():
    """Print the current request states to the console."""
    while True:
        logger.info("Current Request States:")
        for service, state in request_states.items():
            logger.info(f"  {service}: {state['status']} (Success: {state['success_count']}, Errors: {state['error_count']})")
        await asyncio.sleep(10)  # Update every 10 seconds

async def main():
    """Main async function with proper event loop management and state tracking."""
    global seen_movies
    
    # Start the request state printer task
    state_printer_task = asyncio.create_task(print_request_states())
    
    try:
        while True:
            html = await fetch_amazon_page()
            if not html:
                logger.warning("Failed to fetch Amazon page, retrying in 2 seconds")
                await asyncio.sleep(2)
                continue

            movies = extract_movie_data(html)
            new_movies = []

            for movie_name, movie_year, amazon_redirect in movies:
                prime_video_link = convert_to_prime_url(amazon_redirect)

                if prime_video_link:
                    movie_key = f"{movie_name} ({movie_year})"
                    
                    if movie_key not in seen_movies:
                        seen_movies.add(movie_key)
                        audio_languages, poster_url = await fetch_audio_languages_and_poster(prime_video_link)
                        new_movies.append((movie_name, movie_year, prime_video_link, audio_languages, poster_url))
            
            if new_movies:
                logger.info(f"Found {len(new_movies)} new movies")
                for movie_name, movie_year, prime_video_link, audio_languages, poster_url in new_movies:
                    text = (f"🎬 *New Movie:* {movie_name} ({movie_year})\n"
                            f"🔗 [Watch on Prime Video]({prime_video_link})\n"
                            f"🎧 *Audio:* {audio_languages}\n"
                            f"🖼️ *Poster:* [View Poster]({poster_url})")
                    logger.info(f"Sending notification for: {movie_name}")
                    await send_telegram_message(text)
            else:
                logger.info("No new movies found")

            await asyncio.sleep(2)
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}")
    finally:
        state_printer_task.cancel()
        try:
            await state_printer_task
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    logger.info("Starting Prime Video notification bot")
    asyncio.run(main())
