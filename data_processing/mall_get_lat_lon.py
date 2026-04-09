import csv
import urllib.parse
import urllib.request
import json
import time

INPUT_FILE = "../data/raw/malls.csv"
OUTPUT_FILE = "../data/processed/malls_with_coords.csv"

API_URL = "https://www.onemap.gov.sg/api/common/elastic/search"


def geocode(query):
    params = {
        "searchVal": query,
        "returnGeom": "Y",
        "getAddrDetails": "N",
        "pageNum": 1
    }

    url = API_URL + "?" + urllib.parse.urlencode(params)

    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())

            if data["found"] > 0:
                result = data["results"][0]
                return result["LATITUDE"], result["LONGITUDE"]

    except Exception:
        pass

    return None, None


with open(INPUT_FILE, newline='', encoding="utf-8-sig") as infile, \
     open(OUTPUT_FILE, "w", newline='', encoding="utf-8") as outfile:

    reader = csv.DictReader(infile)

    fieldnames = reader.fieldnames + ["lat", "lon"]
    writer = csv.DictWriter(outfile, fieldnames=fieldnames)

    writer.writeheader()

    for row in reader:

        lat, lon = geocode(row["name"])

        if lat is None and row.get("alt_name"):
            lat, lon = geocode(row["alt_name"])

        row["lat"] = lat
        row["lon"] = lon

        writer.writerow(row)

        time.sleep(0.2)
