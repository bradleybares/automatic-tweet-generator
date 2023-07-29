import argparse
import configparser
import json
from pathlib import Path
import shutil
import sys
from typing import Optional, List, Dict
import requests
from loguru import logger

LOCAL_DIRECTORY = Path(__file__).parents[0]
JSON_FILENAME = "downloaded_photos.json"

RANDOM_PHOTO_URL = "https://api.unsplash.com/photos/random"
HEADS = {"Accept-Version": "v1"}
ACCESS_KEY = ""

if not ACCESS_KEY:
    if not (LOCAL_DIRECTORY / "..config.ini").exists():
        config = configparser.ConfigParser()
        config.read("config.ini")
        ACCESS_KEY = config["UNSPLASH"]["ACCESS_KEY"]
    else:
        logger.error(
            "Can't find the Unsplash authentication information. Please check inside the code or config.ini file."
        )
        sys.exit()


class Photo:
    def __init__(self, photographer: str, url: str, link: str):
        self.photographer = photographer
        self.url = url
        self.link = link


def download_photos(photo_directory: Path, photos_to_download: Dict[str, Photo]):
    path_to_json = photo_directory / JSON_FILENAME

    downloaded_photos = {}
    if not photo_directory.exists():
        photo_directory.mkdir()
        with open(path_to_json, "w") as json_file:
            json.dump("{}", json_file, indent=2)
    else:
        with open(path_to_json, "r") as json_file:
            downloaded_photos = json.load(json_file)
        photos_to_download = {
            photo_id: photo
            for photo_id, photo in photos_to_download.items()
            if photo_id not in downloaded_photos
        }

    if not photos_to_download:
        logger.warning("All photos already downloaded.")
        sys.exit()
    else:
        logger.info("Downloading photos.")
        with open(path_to_json, "w") as json_file:
            for photo_id, photo in photos_to_download.items():
                photo_download_response = requests.get(photo.url, stream=True)
                with open(photo_directory / f"{photo_id}.jpg", "wb") as out_file:
                    shutil.copyfileobj(photo_download_response.raw, out_file)
                downloaded_photos[photo_id] = vars(photo)
            json.dump(downloaded_photos, json_file, indent=2)
        logger.success(
            f"Downloaded {len(photos_to_download)} photos to {photo_directory}."
        )


def get_response(url, payload):
    r = requests.get(url, params=payload, headers=HEADS)
    data = json.loads(r.content.decode("utf-8"))
    if r.status_code == 200 and r:
        return data, r.status_code
    logger.error(f"{r.status_code} error - {data['errors'][0]}")
    sys.exit()


def get_photos(
    collections: List[str],
    query: Optional[str],
    orientation: Optional[str],
    size: str,
    count: int,
) -> None:
    response, s = get_response(
        RANDOM_PHOTO_URL,
        {
            "client_id": ACCESS_KEY,
            "collections": collections,
            "query": query,
            "orientation": orientation,
            "count": count,
        },
    )

    logger.info("Collecting photos.")

    photos_to_download = {
        photo["id"]: Photo(
            photographer=photo["user"]["name"],
            url=photo["urls"][size],
            link=photo["links"]["html"],
        )
        for photo in response
    }

    orientation = orientation or "any"
    query = query or "any"
    photo_directory = Path(
        LOCAL_DIRECTORY / f"random-{size}-{orientation}-{query}-photos"
    )
    download_photos(photo_directory, photos_to_download)


def parse_args():
    parser = argparse.ArgumentParser(
        description="All parameters are optional, and can be combined to narrow the pool"
        " of photos from which a random one will be chosen."
    )
    parser.add_argument("--collections", type=str.lower, nargs="+", default=[])
    parser.add_argument(
        "-q",
        "--query",
        type=str.lower,
        help="Limit selection to photos matching a search term.",
    )
    parser.add_argument(
        "-o",
        "--orientation",
        type=str.lower,
        choices=["landscape", "portrait", "squarish"],
        help="Filter by photo orientation.",
    )
    parser.add_argument(
        "-s",
        "--size",
        type=str.lower,
        nargs="?",
        default="regular",
        choices=["raw", "full", "regular", "small", "thumb"],
    )
    parser.add_argument("--count", type=int, default=1)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    get_photos(args.collections, args.query, args.orientation, args.size, args.count)
