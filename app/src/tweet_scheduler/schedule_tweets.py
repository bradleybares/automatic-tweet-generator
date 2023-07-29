import configparser
import json
import os
import random
import sys
from typing import List
import schedule
import time
from loguru import logger
import pandas as pd
import tweepy
import shutil
import datetime
from pprint import pprint
from app.src.quote_overlay.overlay_quotes import *
from app.data.pictures.custom_download import JSON_FILENAME

LOCAL_DIRECTORY = Path(__file__).parents[0]
MEDIA_PATH = LOCAL_DIRECTORY / "media"
CSV_FILENAME = "tweeted.csv"
HASHTAGS = [
    "nft",
    "pixelart",
    "nfts",
    "web3",
    "nftcommunity",
    "forest",
    "nature",
    "qotd",
]
NUM_TAGS = 3
TWEETED_DATAFRAME_COLUMNS = [
    "created_at",
    "tweet_id",
    "photo_id",
    "photographer",
    "link",
    "quote",
    "author",
]

CONSUMER_KEY = ""
CONSUMER_SECRET = ""
ACCESS_TOKEN = ""
ACCESS_TOKEN_SECRET = ""

if not (CONSUMER_KEY and CONSUMER_SECRET and ACCESS_TOKEN and ACCESS_TOKEN_SECRET):
    if not os.path.isfile(LOCAL_DIRECTORY / "..config.ini"):
        config = configparser.ConfigParser()
        config.read("config.ini")
        CONSUMER_KEY = config["TWITTER"]["CONSUMER_KEY"]
        CONSUMER_SECRET = config["TWITTER"]["CONSUMER_SECRET"]
        ACCESS_TOKEN = config["TWITTER"]["ACCESS_TOKEN"]
        ACCESS_TOKEN_SECRET = config["TWITTER"]["ACCESS_TOKEN_SECRET"]
        BEARER_TOKEN = config["TWITTER"]["BEARER_TOKEN"]
    else:
        logger.error(
            "Cannot find the Twitter authentication information. Please check inside the code or config.ini file."
        )
        sys.exit()


class Tweet:
    def __init__(
        self,
        pid: str,
        photographer: str,
        link: str,
        quote: str,
        author: str,
        image_path: Path,
        msg: str,
    ):
        self.pid = pid
        self.photographer = photographer
        self.link = link
        self.quote = quote
        self.author = author
        self.image_path = image_path
        self.msg = msg


def create_api():
    auth = tweepy.OAuth1UserHandler(
        CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET
    )
    return tweepy.API(auth)

def create_client():
    return tweepy.Client(BEARER_TOKEN, CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)


def post_tweet(tweet: Tweet, photos_dir: Path, quotes_path: Path) -> None:
    logger.info("Posting Tweet")

    # Instantiate API
    api = create_api()

    # Upload Media
    media = api.simple_upload(tweet.image_path)
    logger.success("Uploaded Media")

    # Instantiate Client
    client = create_client()

    # Tweet Message w/ attached media
    response = client.create_tweet(text=tweet.msg, media_ids=[media.media_id])
    logger.success("Posted Tweet")

    # Update Tweeted Doc
    csv_path = LOCAL_DIRECTORY / CSV_FILENAME
    tweeted_df = pd.read_csv(csv_path)
    tweet_info = pd.Series(
        data=[
            str(datetime.datetime.now()),
            response.id,
            tweet.pid,
            tweet.photographer,
            tweet.link,
            tweet.quote,
            tweet.author,
        ],
        index=TWEETED_DATAFRAME_COLUMNS,
    )
    pd.concat([tweeted_df, tweet_info.to_frame(1).T], ignore_index=True).to_csv(
        csv_path, index=False
    )
    logger.success("Updated Tweet Tracker")

    # Cleanup photo and quote
    logger.info("Removing Photo and Quote")
    Path(photos_dir / f"{tweet.pid}.jpg").unlink()
    tweet.image_path.unlink()
    quotes_df = pd.read_csv(quotes_path)
    quotes_df[~quotes_df.Quote.str.contains(tweet.quote)].to_csv(
        quotes_path, index=False
    )


def prepare_tweets(photos_dir: Path, quotes_path: Path, count: int) -> List[Tweet]:
    logger.info(f"Preparing {count} tweets")
    # Get Quote Info
    try:
        quotes_df = pd.read_csv(quotes_path).head(count)
    except IndexError:
        logger.error(f"Not enough quotes to satisfy request for {count} tweets")
        sys.exit()

    # Get Image Paths
    try:
        path_generator = photos_dir.glob("*.jpg")
        image_paths = [next(path_generator) for _ in range(count)]
    except StopIteration:
        logger.error(f"Not enough images to satisfy request for {count} tweets")
        sys.exit()

    # Read DataFrame
    csv_path = LOCAL_DIRECTORY / CSV_FILENAME
    try:
        tweeted_df = pd.read_csv(csv_path)
    except FileNotFoundError:
        tweeted_df = pd.DataFrame(columns=TWEETED_DATAFRAME_COLUMNS)
        tweeted_df.to_csv(csv_path, index=False)

    Path.mkdir(MEDIA_PATH, exist_ok=True)
    tweets = []
    for i in range(count):
        # Create Image
        quote = quotes_df["Quote"][i]
        author = quotes_df["Author"][i]
        save_path = Path(LOCAL_DIRECTORY / "media" / f"{i}.jpg")
        logger.info(f"Composing {save_path.name}")
        compose(
            img_path=image_paths[i], quote=quote, author=author, save_path=save_path
        )

        # Get Photo information
        with open(photos_dir / JSON_FILENAME, "r") as json_file:
            downloaded_photos = json.load(json_file)
        pid = image_paths[i].stem
        photographer = downloaded_photos[pid]["photographer"]
        link = downloaded_photos[pid]["link"]

        # Construct Message
        msg = (
            f"Quote Of The Day #{tweeted_df.shape[0] + i + 1}\n\n"
            f"📷: {photographer}\n"
        )

        if len(msg) < 260 - len(link):
            msg += f"{link}\n\n"

        selected_tags = []
        while (
            len(msg) < 260 - len(min(HASHTAGS, key=len)) + 2
            and len(selected_tags) < NUM_TAGS
        ):
            selected_tag = random.choice(
                [
                    tag
                    for tag in HASHTAGS
                    if len(tag) + 2 <= 260 - len(msg) and tag not in selected_tags
                ]
            )
            msg += f"#{selected_tag} "
            selected_tags.append(selected_tag)

        # Package Tweet Object
        tweets.append(
            Tweet(
                pid=pid,
                photographer=photographer,
                link=link,
                quote=quote,
                author=author,
                image_path=save_path,
                msg=msg,
            )
        )

    logger.success(f"{count} tweets prepared")

    return tweets


def schedule_tweets(photos_dir: Path, quotes_path: Path, count: int, tweet_time: str) -> None:
    tweets = prepare_tweets(photos_dir, quotes_path, count)

    for tweet in tweets:
        pprint({"image": str(tweet.image_path.name), "msg": tweet.msg})
    tweets_reviewed_input = input(
        "Please review the created tweets. If you are satisfied and would like to schedule them type 'yes': "
    )

    if tweets_reviewed_input == "yes":
        schedule.every().day.at(tweet_time).do(
            lambda: post_tweet(
                tweet=tweets.pop(0), photos_dir=photos_dir, quotes_path=quotes_path
            )
        )
        try:
            while tweets:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\n KeyboardInterrupt detected -- exiting now")

    logger.info("Cleaning Artifacts")
    shutil.rmtree(MEDIA_PATH)


def parse_args():
    parser = argparse.ArgumentParser(
        description="All parameters are optional, and can be combined to narrow the pool"
        " of photos from which a random one will be chosen."
    )
    parser.add_argument("--photos-dir", required=True, type=Path, help="Path to the photos directory.")
    parser.add_argument("--quotes-path", required=True, type=str, help="Path to the quotes file.")
    parser.add_argument("-c", "--count", required=True, type=int, help="Number of tweets to schedule.")
    parser.add_argument("-t", "--tweet-time", default="11:30", type=str, help="Time to schedule the tweets.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    schedule_tweets(args.photos_dir, args.quotes_path, args.count, args.tweet_time)
