from itertools import cycle
import tweepy
import moondream as md
from PIL import Image
import requests
from io import BytesIO
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# Load Moondream API keys into a list
MOONDREAM_API_KEYS = [
    os.getenv(f"MOONDREAM_API_KEY_{i}") for i in range(1, 6)  # Adjust range as needed
]

# Cycle through the Moondream API keys
moondream_keys_cycle = cycle(MOONDREAM_API_KEYS)

def get_new_moondream_model():
    """
    Rotate to the next Moondream API key and return a new model instance.
    """
    new_key = next(moondream_keys_cycle)
    print(f"Using Moondream API key: {new_key}")
    return md.vl(api_key=new_key)

# Twitter API configuration (unchanged)
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
BOT_USER_ID = "1871746331212992512"  # Replace with your bot's user ID

def download_image(url):
    response = requests.get(url)
    if response.status_code == 200:
        return Image.open(BytesIO(response.content))
    return None

def process_mention(mention, includes):
    try:
        print(f"Processing Tweet ID: {mention.id}")

        # Fetch author username from includes
        author_username = None
        if includes and "users" in includes:
            author_id = mention.author_id
            user_data = next(
                (user for user in includes["users"] if user["id"] == str(author_id)),
                None
            )
            if user_data:
                author_username = user_data["username"]

        # Debug author username
        if author_username:
            print(f"Author Username: {author_username}")
        else:
            print(f"Unable to fetch username for author_id: {mention.author_id}")

        # Media processing logic
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
                        # Rotate Moondream key for each request
                        model = get_new_moondream_model()
                        try:
                            answer = model.query(image, query)["answer"]
                            print(f"Generated Answer: {answer}")

                            # Construct reply text with author username
                            if author_username:
                                reply_text = f"@{author_username} Answer: {answer}"
                            else:
                                reply_text = f"Answer: {answer}"  # Fallback if username is unavailable

                            # Post the reply
                            response = client.create_tweet(
                                text=reply_text,
                                in_reply_to_tweet_id=mention["id"]
                            )
                            print(f"Reply posted: {response}")
                        except Exception as e:
                            print(f"Error querying Moondream API: {e}")
                    else:
                        print(f"Failed to download image for mention: {mention.id}")
                else:
                    print(f"No valid media URL for mention: {mention.id}")
            else:
                print(f"No photo attachment found for mention: {mention.id}")
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
    except Exception as e:
        print(f"Error fetching mentions: {e}")

if __name__ == "__main__":
    run_bot()