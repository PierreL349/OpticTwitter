from itertools import cycle
import tweepy
import moondream as md
from PIL import Image
import requests
from io import BytesIO
from dotenv import load_dotenv
import os
import time

# Load .env file
load_dotenv()

# Load Moondream API keys into a list
MOONDREAM_API_KEYS = [
    os.getenv(f"MOONDREAM_API_KEY_{i}") for i in range(1, 6)  # Adjust range as needed
]

# Cycle through the Moondream API keys
moondream_keys_cycle = cycle(MOONDREAM_API_KEYS)

def get_valid_moondream_model():
    while True:
        new_key = next(moondream_keys_cycle)
        print(f"Trying Moondream API key: {new_key}")
        model = md.vl(api_key=new_key)
        try:
            model.query("test", "valid")
            return model
        except Exception as e:
            print(f"Invalid Moondream API key: {new_key}. Error: {e}")
            continue

# Twitter API configuration
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

client = tweepy.Client(
    bearer_token=TWITTER_BEARER_TOKEN,
    consumer_key=TWITTER_API_KEY,
    consumer_secret=TWITTER_API_SECRET,
    access_token=TWITTER_ACCESS_TOKEN,
    access_token_secret=TWITTER_ACCESS_SECRET,
)

BOT_HANDLE = "optic_agent"
BOT_USER_ID = "1871746331212992512"

def download_image(url):
    response = requests.get(url)
    if response.status_code == 200:
        return Image.open(BytesIO(response.content))
    return None

def process_mention(mention, includes):
    try:
        print(f"Processing Tweet ID: {mention.id}")
        author_username = None
        if includes and "users" in includes:
            author_id = mention.author_id
            user_data = next(
                (user for user in includes["users"] if user["id"] == str(author_id)),
                None
            )
            if user_data:
                author_username = user_data["username"]

        if "attachments" in mention and "media_keys" in mention["attachments"]:
            media_keys = mention["attachments"]["media_keys"]
            media = next(
                (media for media in includes.get("media", []) if media.media_key in media_keys),
                None
            )
            if media and media.type == "photo":
                media_url = media.url
                print(f"Media URL: {media_url}")
                if media_url:
                    image = download_image(media_url)
                    if image:
                        query = mention["text"].replace(BOT_HANDLE, "").strip()
                        model = get_valid_moondream_model()
                        try:
                            answer = model.query(image, query)["answer"]
                            print(f"Generated Answer: {answer}")
                            if author_username:
                                reply_text = f"@{author_username} Answer: {answer}"
                            else:
                                reply_text = f"Answer: {answer}"
                            response = client.create_tweet(
                                text=reply_text,
                                in_reply_to_tweet_id=mention["id"]
                            )
                            print(f"Reply posted: {response}")
                        except Exception as e:
                            print(f"Error querying Moondream API: {e}")
    except Exception as e:
        print(f"Error processing mention ID {mention.id}: {e}")

def get_last_seen_id(file_name="last_seen_id.txt"):
    try:
        with open(file_name, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

def set_last_seen_id(last_seen_id, file_name="last_seen_id.txt"):
    with open(file_name, "w") as f:
        f.write(str(last_seen_id))

def run_bot():
    print("Bot started. Checking for mentions...")
    while True:
        try:
            last_seen_id = get_last_seen_id()
            response = client.get_users_mentions(
                id=BOT_USER_ID,
                expansions="attachments.media_keys",
                media_fields="url,type",
                max_results=10,
                since_id=last_seen_id
            )
            if response.data:
                for mention in response.data:
                    process_mention(mention, response.includes)
                newest_id = response.meta["newest_id"]
                set_last_seen_id(newest_id)
            else:
                print("No new mentions found.")
            print("Sleeping for 60 seconds before checking for mentions again...")
            time.sleep(60)
        except tweepy.TooManyRequests as e:
            print(f"Rate limit hit. Sleeping until reset...")
            reset_time = int(e.response.headers.get("x-rate-limit-reset", time.time()))
            wait_time = reset_time - int(time.time())
            if wait_time > 0:
                print(f"Sleeping for {wait_time} seconds to comply with rate limits...")
                time.sleep(wait_time)
        except Exception as e:
            print(f"Error fetching mentions: {e}")
            print("Sleeping for 30 seconds before retrying...")
            time.sleep(30)

if __name__ == "__main__":
    run_bot()