import argparse
import math
import textwrap
from pathlib import Path

from PIL import Image, ImageStat, ImageFont, ImageDraw, ImageOps

LOCAL_DIRECTORY = Path(__file__).parents[0]

FONT_SIZE_RATIO = 48 / 792
VERTICAL_TEXT_PADDING = 0
LANDSCAPE_HORIZONTAL_TEXT_PADDING = 10
PORTRAIT_HORIZONTAL_TEXT_PADDING = 5
WATERMARK_SIZE_RATIO = (150 * 150) / (1920 * 1080)
WATERMARK_PADDING_RATIO = 1 / 5
WATERMARK_OUTLINE_RATIO = 1 / 40
DARK_OPAQUE = (53, 56, 57, 250)
DARK_TRANSPARENT = (53, 56, 57, 190)
LIGHT_OPAQUE = (248, 248, 255, 250)
LIGHT_TRANSPARENT = (248, 248, 255, 190)


def draw_text_box(img: Image, dark: bool, msg: str, author: str):
    msg = f'"{msg}"'
    author = f"- {author}"

    msg_font_size = int(img.height * FONT_SIZE_RATIO)
    with open(LOCAL_DIRECTORY / "PatrickHand-Regular.ttf", "rb") as font:
        msg_font = ImageFont.truetype(font, msg_font_size)
    with open(LOCAL_DIRECTORY / "PatrickHand-Regular.ttf", "rb") as font:
        author_font = ImageFont.truetype(font, int(msg_font_size * 3 / 4))

    msg_width, msg_height = msg_font.getsize(msg)
    author_width, author_height = author_font.getsize(author)

    text_box_character_width = int(
        (img.width / (msg_width / len(msg)))
        - (
            (
                PORTRAIT_HORIZONTAL_TEXT_PADDING
                if img.height > img.width
                else LANDSCAPE_HORIZONTAL_TEXT_PADDING
            )
            * 2
        )
    )
    wrapped_msg = textwrap.wrap(msg, width=text_box_character_width)

    if dark:
        text_fill = DARK_OPAQUE
        box_fill = LIGHT_TRANSPARENT
    else:
        text_fill = LIGHT_OPAQUE
        box_fill = DARK_TRANSPARENT

    line_height = msg_height * (1 + VERTICAL_TEXT_PADDING / len(wrapped_msg))
    wrapped_message_height = line_height * len(wrapped_msg)
    y = (img.height - wrapped_message_height - author_height) / 2
    wrapped_msg_width = 0

    draw = ImageDraw.Draw(img, "RGBA")
    draw.rectangle(
        [(0, y), (img.width, y + wrapped_message_height + author_height)], fill=box_fill
    )

    for line in wrapped_msg:
        line_width, _ = msg_font.getsize(line)
        draw.text(
            ((img.width - line_width) / 2, y), line, font=msg_font, fill=text_fill
        )
        y += line_height
        wrapped_msg_width = max(wrapped_msg_width, line_width)

    draw.text(
        (
            (img.width - wrapped_msg_width) / 2 + wrapped_msg_width - author_width,
            y - (line_height - author_height) / 2,
        ),
        author,
        font=author_font,
        fill=text_fill,
    )


def apply_watermark(img: Image, dark: bool, watermark: Image):
    area = img.width * img.height * WATERMARK_SIZE_RATIO
    edge = int(math.sqrt(area))
    size = (edge, edge)

    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0) + size, fill=255)

    resized_watermark = ImageOps.fit(watermark, size, centering=(0.5, 0.5))
    resized_watermark.putalpha(mask)

    padding = int(edge * WATERMARK_PADDING_RATIO)
    x = padding
    y = img.height - edge - padding
    pos = (x, y)

    img.paste(resized_watermark, pos, resized_watermark)

    if dark:
        outline = LIGHT_TRANSPARENT
    else:
        outline = DARK_TRANSPARENT

    ImageDraw.Draw(img, "RGBA").ellipse(
        [(x, y), (x + edge, y + edge)],
        outline=outline,
        width=int(edge * WATERMARK_OUTLINE_RATIO),
    )


def compose(
    img_path: Path,
    quote: str,
    author: str,
    save_path: Path,
    watermark_path: Path = Path(LOCAL_DIRECTORY / "logo.png"),
):
    img = Image.open(img_path)
    watermark = Image.open(watermark_path)

    hsl = img.convert("L")
    hsl_stat = ImageStat.Stat(hsl)
    dark = hsl_stat.mean[0] <= 127

    draw_text_box(img, dark, quote, author)

    apply_watermark(img, dark, watermark)

    img.save(save_path)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Provide the desired information to create a quoted image."
    )
    parser.add_argument("-i", "--image", type=Path, help="Path to image.")
    parser.add_argument("-q", "--quote", type=str, help="Quote to be displayed.")
    parser.add_argument("-a", "--author", type=str, help="Author of the quote.")
    parser.add_argument(
        "-w",
        "--watermark",
        type=Path,
        default="./logo.png",
        help="Path to the watermark.",
    )
    parser.add_argument("-s", "--save", type=Path, help="Path to save the ensemble.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    compose(args.image, args.quote, args.author, args.watermark, args.save)
