import aiohttp
import asyncio
import requests
from dotenv import load_dotenv
import hashlib
import os
import json
import argparse
import time
from rich.console import Console
from rich.progress import Progress
import csv
from datetime import datetime
import logging
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import sys



console = Console()

load_dotenv()
listURL = os.getenv("LIST_URL")
listFileName = os.getenv("LIST_FILENAME")
proxy = os.getenv("PROXY") if os.getenv("USE_PROXY") == "TRUE" else None
proxies = {"http": proxy, "https": proxy} if os.getenv("USE_PROXY") == "TRUE" else None
logging.basicConfig(
    filename=os.getenv("LOG_FILENAME"),
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
requests.packages.urllib3.disable_warnings()


# Perform a Sync Request and return response details
def do_sync_request(method, url):
    response = requests.request(
        method=method,
        url=url,
        proxies=proxies,
        timeout=args.timeout,
        verify=False,
    )
    parsedData = None
    try:
        parsedData = response.json()
    except Exception as e:
        logError(e, f"Error in Sync HTTP Request [{method}] {url}")
    return response, parsedData


# Perform an Async Request and return response details
async def do_async_request(method, url, session):
    try:
        response = await session.request(
            method,
            url,
            proxy=proxy,
            timeout=args.timeout,
            allow_redirects=True,
            ssl=False,
        )

        content = await response.text()
        responseData = {
            "url": url,
            "status_code": response.status,
            "headers": response.headers,
            "content": content,
        }
        return responseData
    except Exception as e:
        logError(e, f"Error in Async HTTP Request [{method}] {url}")
        return None


# Read list file and return content
def readList():
    with open(listFileName, "r", encoding="UTF-8") as f:
        data = json.load(f)
    return data


# Download .JSON file list from defined URL
def downloadList():
    response, parsedData = do_sync_request("GET", listURL)
    with open(listFileName, "w", encoding="UTF-8") as f:
        json.dump(parsedData, f, indent=4, ensure_ascii=False)


# Return MD5 HASH for given JSON
def hashJSON(jsonData):
    dumpJson = json.dumps(jsonData, sort_keys=True)
    jsonHash = hashlib.md5(dumpJson.encode("utf-8")).hexdigest()
    return jsonHash


# Log error in CLI and log file
def logError(e, message):
    if str(e) != "":
        error = str(e)
    else:
        error = repr(e)
    logging.error(f"{message} | {error}")
    if args.verbose:
        console.print(f"⛔  {message}")
        console.print("     | An error occurred:")
        console.print(f"     | {error}")


# Save results to CSV file
def saveToCsv(username, date, results):
    try:
        fileName = username + "_" + date + "_blackbird.csv"
        with open(
            fileName,
            "w",
            newline="",
        ) as file:
            writer = csv.writer(file)
            writer.writerow(["name", "url"])
            for result in results:
                writer.writerow([result["name"], result["url"]])
        console.print(f"💾  Saved results to '[cyan1]{fileName}[/cyan1]'")
    except Exception as e:
        logError(e, "Coudn't saved results to CSV file!")

# Save results to PDF file
def saveToPdf(username, prettyDate, date, results):
    pdfmetrics.registerFont(TTFont('Montserrat', 'assets\\Montserrat-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('Montserrat-Bold', 'assets\\Montserrat-Bold.ttf'))

    fileName = username + "_" + date + "_blackbird.pdf"
    width, height = letter
    canva = canvas.Canvas(fileName, pagesize=letter)
    accountsCount = len(results)

    canva.drawImage("assets\\blackbird-logo.png", 35, height - 90, width=60, height=60)
    canva.setFont("Montserrat-Bold", 15)
    canva.drawCentredString((width / 2) - 5, height - 70, "Report")
    canva.setFont("Montserrat", 7)
    canva.drawString(width - 90, height - 70, prettyDate)
    canva.setFont("Montserrat", 5)
    canva.drawString(width - 185, height - 25, "This report was generated using the Blackbird OSINT Tool.")
    
    canva.setFillColor("#EDEBED");
    canva.setStrokeColor("#BAB8BA");
    canva.rect(40, height - 160, 530, 35, stroke=1, fill=1);
    canva.setFillColor("#000000");
    usernameWidth = stringWidth(username, "Montserrat-Bold", 11)
    canva.drawImage("assets\\correct.png", (width / 2) - ((usernameWidth / 2) + 15)  , height - 147, width=10, height=10, mask='auto')
    canva.setFont("Montserrat-Bold", 11)
    canva.drawCentredString(width / 2, height - 145, username)    

    canva.setFillColor("#FFF8C5");
    canva.setStrokeColor("#D9C884");
    canva.rect(40, height - 210, 530, 35, stroke=1, fill=1);
    canva.setFillColor("#57523f")
    canva.setFont("Montserrat", 8)
    canva.drawImage("assets\\warning.png", 55, height - 197, width=10, height=10, mask='auto')
    canva.drawString(70, height - 195, "Blackbird can make mistakes. Consider checking the information.")

    if (accountsCount >= 1):
        canva.setFillColor("#000000");
        canva.setFont("Montserrat", 15)
        canva.drawImage("assets\\arrow.png", 40, height - 240, width=12, height=12, mask='auto')
        canva.drawString(55, height - 240, f"Results ({accountsCount})")
        
        y_position = height - 270
        for result in results:
            if y_position < 72:
                canva.showPage()
                y_position = height - 130
            canva.setFont("Montserrat", 12)
            canva.drawString(72, y_position, f"• {result['name']}")
            siteWidth = stringWidth(f"• {result['name']}", "Montserrat", 12)
            canva.drawImage("assets\\link.png", 77 + siteWidth, y_position, width=10, height=10, mask='auto')
            canva.linkURL(result['url'], (77 + siteWidth, y_position, 77 + siteWidth + 10, y_position + 10), relative=1)
            y_position -= 25 

    canva.save()
    console.print(f"💾  Saved results to '[cyan1]{fileName}[/cyan1]'")


def filterFoundAccounts(site):
    if site["status"] == "FOUND":
        return True
    else:
        return False


# Verify account existence based on list args
async def checkSite(site, method, url, session):
    returnData = {"name": site["name"], "url": url, "status": "NONE"}
    response = await do_async_request(method, url, session)
    if response == None:
        returnData["status"] = "ERROR"
        return returnData
    try:
        if response:
            if (site["e_string"] in response["content"]) and (
                site["e_code"] == response["status_code"]
            ):
                if (site["m_string"] not in response["content"]) and (
                    site["m_code"] != response["status_code"]
                ):
                    returnData["status"] = "FOUND"
                    console.print(
                        f"  ✔️  \[[cyan1]{site['name']}[/cyan1]] [bright_white]{response['url']}[/bright_white]"
                    )
            else:
                returnData["status"] = "NOT-FOUND"
                if args.verbose:
                    console.print(
                        f"  ❌ [[blue]{site['name']}[/blue]] [bright_white]{response['url']}[/bright_white]"
                    )
            return returnData
    except Exception as e:
        logError(e, f"Coudn't check {site['name']} {url}")
        return returnData


# Control survey on list sites
async def fetchResults(username):
    data = readList()
    async with aiohttp.ClientSession() as session:
        tasks = []
        for site in data["sites"]:
            tasks.append(
                checkSite(
                    site=site,
                    method="GET",
                    url=site["uri_check"].replace("{account}", username),
                    session=session,
                )
            )
        tasksResults = await asyncio.gather(*tasks, return_exceptions=True)
        dateRaw = datetime.now().strftime("%m_%d_%Y")
        datePretty = datetime.now().strftime("%B %d, %Y")
        results = {
            "results": tasksResults,
            "username": username,
            "date": dateRaw,
            "pretty-date": datePretty
        }
    return results


# Start username check and presents results to user
def verifyUsername(username):
    console.print(
        f':play_button: Enumerating accounts with username "[cyan1]{username}[/cyan1]"'
    )
    start_time = time.time()
    results = asyncio.run(fetchResults(username))
    end_time = time.time()
    console.print(
        f":chequered_flag: Check completed in {round(end_time - start_time, 1)} seconds ({len(results['results'])} sites)"
    )
    foundAccounts = list(filter(filterFoundAccounts, results["results"]))
    if (len(foundAccounts) > 0):
        if args.csv:
            saveToCsv(results["username"], results["date"], foundAccounts)

        if args.pdf:
            saveToPdf(results["username"], results["pretty-date"], results["date"], foundAccounts)
    else:
        console.print("⭕ No accounts were found for the given username")


# Check for changes in remote list
def checkUpdates():
    if os.path.isfile(listFileName):
        console.print(":counterclockwise_arrows_button: Checking for updates...")
        try:
            data = readList()
            currentListHash = hashJSON(data)
            response, data = do_sync_request("GET", listURL)
            remoteListHash = hashJSON(data)
            if currentListHash != remoteListHash:
                console.print(":counterclockwise_arrows_button: Updating...")
                downloadList()
            else:
                console.print("✔️  List is up to date")
        except Exception as e:
            console.print(":police_car_light: Coudn't read local list")
            console.print(":down_arrow: Downloading WhatsMyName list")
            downloadList()
    else:
        console.print(":globe_with_meridians: Downloading WhatsMyName list")
        downloadList()


if __name__ == "__main__":
    console.print(
        """[red]
    ▄▄▄▄    ██▓    ▄▄▄       ▄████▄   ██ ▄█▀ ▄▄▄▄    ██▓ ██▀███  ▓█████▄ 
    ▓█████▄ ▓██▒   ▒████▄    ▒██▀ ▀█   ██▄█▒ ▓█████▄ ▓██▒▓██ ▒ ██▒▒██▀ ██▌
    ▒██▒ ▄██▒██░   ▒██  ▀█▄  ▒▓█    ▄ ▓███▄░ ▒██▒ ▄██▒██▒▓██ ░▄█ ▒░██   █▌
    ▒██░█▀  ▒██░   ░██▄▄▄▄██ ▒▓▓▄ ▄██▒▓██ █▄ ▒██░█▀  ░██░▒██▀▀█▄  ░▓█▄   ▌
    ░▓█  ▀█▓░██████▒▓█   ▓██▒▒ ▓███▀ ░▒██▒ █▄░▓█  ▀█▓░██░░██▓ ▒██▒░▒████▓ 
    ░▒▓███▀▒░ ▒░▓  ░▒▒   ▓▒█░░ ░▒ ▒  ░▒ ▒▒ ▓▒░▒▓███▀▒░▓  ░ ▒▓ ░▒▓░ ▒▒▓  ▒ 
    ▒░▒   ░ ░ ░ ▒  ░ ▒   ▒▒ ░  ░  ▒   ░ ░▒ ▒░▒░▒   ░  ▒ ░  ░▒ ░ ▒░ ░ ▒  ▒ 
    ░    ░   ░ ░    ░   ▒   ░        ░ ░░ ░  ░    ░  ▒ ░  ░░   ░  ░ ░  ░ 
    ░          ░  ░     ░  ░░ ░      ░  ░    ░       ░     ░        ░    
        ░                  ░                     ░               ░      

    [/red]"""
    )
    console.print(
        "[white]Made with :beating_heart: by Lucas Antoniaci ([red]p1ngul1n0[/red])[/white]"
    )

    parser = argparse.ArgumentParser(
        prog="blackbird",
        description="An OSINT tool to search for accounts by username in social networks.",
    )
    parser.add_argument("-u", "--username", help="The given username to search.")
    parser.add_argument("--csv", default=False, action=argparse.BooleanOptionalAction, help="Generate a CSV with the results.")
    parser.add_argument("--pdf", default=False, action=argparse.BooleanOptionalAction, help="Generate a PDF with the results.")
    parser.add_argument(
        "-v", "--verbose", default=False, action=argparse.BooleanOptionalAction, help="Show verbose output."
    )
    parser.add_argument("-t", "--timeout", type=int, default=30, help="Timeout in seconds for each HTTP request (Default is 30).")
    parser.add_argument("--no-update", action="store_true", help="Don't update sites lists.")
    parser.add_argument('-a', '--about', action='store_true', help='Show about information and exit.')

    args = parser.parse_args()

    if args.about:
        console.print("""
        Author: Lucas Antoniaci (p1ngul1n0)
        Description: This tool search for accounts using data from the WhatsMyName project, which is an open-source tool developed by WebBreacher.
        WhatsMyName License: The WhatsMyName project is licensed under the Creative Commons Attribution-ShareAlike 4.0 International License (CC BY-SA 4.0).
        WhatsMyName Project: https://github.com/WebBreacher/WhatsMyName
        """)
        sys.exit()


    if not args.username:
        parser.error("--username is required.")

    if args.no_update:
        console.print(":next_track_button:  Skipping update...")
    else:
        checkUpdates()

    if args.username:
        verifyUsername(args.username)
