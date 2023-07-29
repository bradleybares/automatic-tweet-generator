from pathlib import Path

import pandas as pd
from requests_html import HTMLSession

LOCAL_DIRECTORY = Path(__file__).parents[0]

if __name__ == "__main__":
    session = HTMLSession()
    r = session.get("https://www.walkmyworld.com/posts/forest-quotes")
    r.html.render()
    quotation_marks = ['"', "“", "”"]
    quotes = [
        e.text.translate(str.maketrans("", "", '"“”'))
        for e in r.html.find("h2")
        if any(mark in e.text for mark in quotation_marks)
    ]
    authors = [e.text.replace("- ", "") for e in r.html.find("em") if len(e.text) > 0]
    table = {"Quote": quotes, "Author": authors}
    df = pd.DataFrame(table)
    df.to_csv(LOCAL_DIRECTORY / "quotes.csv", index=False)
