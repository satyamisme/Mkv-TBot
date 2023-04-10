#!/usr/bin/env python

import re
import io
import os
import logging
from logging import FileHandler, StreamHandler, INFO, basicConfig, error as log_error, info as log_info
from logging.handlers import RotatingFileHandler
from PIL import Image
import configparser
import requests
from bs4 import BeautifulSoup

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from playwright.sync_api import Playwright, sync_playwright

# Logging Utils
basicConfig(
    level=INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s [%(filename)s:%(lineno)d]",
    datefmt="%d-%b-%y %I:%M:%S %p",
    handlers=[
        RotatingFileHandler(
            "log.txt", maxBytes=50000000, backupCount=10
        ),
        StreamHandler(),
    ],
)

logging.getLogger("pyrogram").setLevel(logging.ERROR)
LOG = logging.getLogger(__name__)

# Load config file using configparser
config = configparser.ConfigParser()
config.read('config.env')

# Get environment variables from config file
api_id = int(config['Telegram']['API_ID'])
api_hash = config['Telegram']['API_HASH']
bot_token = config['Telegram']['BOT_TOKEN']

# Create a new Pyrogram client
app = Client("Mkv-TBot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

MKV_DOMAIN = "https://ww3.mkvcinemas.lat"

def scrape(query):
    # Construct the URL for the search query
    url = f"{MKV_DOMAIN}/?s={query}"
    response = requests.get(url)

    # Parse the HTML content of the website using BeautifulSoup
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find the first element that has both "ml-mask" and "jt" as its class attributes
    elems = soup.find_all(class_=["ml-mask", "jt"])
    LOG.info(elems)
    # Extract the href, title, and thumbnail attributes from the first element
    if elems:
        href = elems[0].get('href')
        title = elems[0].get('oldtitle')
        if href:
            resp = requests.get(href)
            nsoup = BeautifulSoup(resp.content, 'html.parser')
            thumb = nsoup.find('meta', {'property': 'og:image'})
            thumbnail = thumb['content']
            LOG.info(thumbnail)

        # Return a dictionary containing the href, title, and thumbnail
        if title and href:
            return {'href': href, 'title': title, 'thumbnail': thumbnail}
    return None

@app.on_message(filters.command('search'))
async def search(client: Client, message: Message):
    # Get the search query from the message text and replace spaces with '+'
    try:
        query = message.text.split(' ', 1)[1].replace(' ', '+')
    except IndexError:
        await message.reply_text("Please provide a search query.")
        return

    # Scrape the website for the first search result
    search_result = scrape(query)
    LOG.info(search_result)

    # Send the search result as a reply to the user
    if search_result:
        caption = f"Title: {search_result['title']}\nLink: {search_result['href']}"
        if search_result['thumbnail']:
            # Check if the "thumbnails" directory exists and create it if it doesn't
            if not os.path.exists("thumbnails"):
                os.makedirs("thumbnails")
            # Download the image from the URL using requests
            image_url = search_result['thumbnail']
            response = requests.get(image_url)
            image_data = response.content
            # Save the image as a thumbnail in a folder called "thumbnails"
            thumbnail_filename = os.path.basename(image_url)
            thumbnail_path = os.path.join("thumbnails", thumbnail_filename)
            with open(thumbnail_path, "wb") as f:
                f.write(image_data)
            # Send the thumbnail with the caption to the chat
            await message.reply_photo(photo=thumbnail_path, caption=caption)
            os.remove(thumbnail_path)
        else:
            await message.reply_text(caption, disable_web_page_preview=True)
    else:
        await message.reply_text("No search results found.")

# Define the command handler
@app.on_message(filters.command("latest"))
def take_screenshot(client, message):
    # Get the URL of the webpage
    url = f"{MKV_DOMAIN}/category/all-movies-and-tv-shows/"

    # Launch the browser with Playwright
    with sync_playwright() as playwright:
        browser_type = playwright.chromium
        browser = browser_type.launch()
        page = browser.new_page()

        # Navigate to the webpage
        page.goto(url)

        # Set the viewport size to the dimensions of the webpage
        content_size = page.evaluate(
            "() => ({ width: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight })"
        )
        page.set_viewport_size(content_size)

        # Take a screenshot of the entire page
        screenshot = page.screenshot(full_page=True)

        # Close the browser
        browser.close()

    # Convert the screenshot to a PIL Image
    img = Image.open(io.BytesIO(screenshot))

    # Send the screenshot to the user
    with io.BytesIO() as bio:
        img.save(bio, 'PNG')
        bio.seek(0)
        client.send_photo(
            chat_id=message.chat.id,
            photo=bio,
            caption="Screenshot of the latest version of the webpage",
        )

# Define a command handler for "/links" command
@app.on_message(filters.command("links"))
def get_links(client, message):
    # Get the URL from the command arguments
    try:
        url = message.text.split(" ", 1)[1]
    except IndexError:
        message.reply_text("Please provide a Link.")
        return

    # Fetch the HTML content of the URL
    response = requests.get(url)
    html_content = response.text

    # Parse the HTML content using BeautifulSoup
    soup = BeautifulSoup(html_content, "html.parser")

    # Find all the links with the class "gdlink"
    gdlinks = soup.find_all("a", class_="gdlink")

    if gdlinks:
        # Define regular expressions to match the resolution of the video
        pattern_480p = re.compile(r"\b480p\b", re.IGNORECASE)
        pattern_720p = re.compile(r"\b720p\b", re.IGNORECASE)
        pattern_1080p = re.compile(r"\b1080p\b", re.IGNORECASE)

        # Initialize a dictionary to store the links by resolution
        links = {"480p": [], "720p": [], "1080p": [], "Unknown": []}

        # Loop through each link and categorize them based on the resolution
        for link in gdlinks:
            href = link.get("href")
            title = link.get("title")
            if "s0" in title.lower():
                resolution = None
                if pattern_480p.search(title):
                    resolution = "480p"
                elif pattern_720p.search(title):
                    resolution = "720p"
                elif pattern_1080p.search(title):
                    resolution = "1080p"
                else:
                    resolution = "Unknown"
                links[resolution].append((title, href))

        # Send the links and titles in each category as separate messages
        if any(links.values()):
            for resolution, link_list in links.items():
                if link_list:
                    response_msg = f"{resolution} links:\n"
                    for i, (title, href) in enumerate(link_list, start=1):
                        response_msg += f"{i}. <a href='{href}'>{title}</a>\n"
                    message.reply_text(response_msg, disable_web_page_preview=True)
        else:
            # Prepare a response message for "gdlink" class links
            response_msg = ""
            for i, gdlink in enumerate(gdlinks, start=1):
                title = gdlink.text.strip()
                hyperlink = gdlink["href"]
                response_msg += f'{i}. [{title}]({hyperlink})\n'
            message.reply_text(response_msg, disable_web_page_preview=True)
    else:
        # Find all links that contain f"{MKV_DOMAIN}?"
        all_links = soup.find_all("a", href=lambda href: href and f"{MKV_DOMAIN}?" in href)

        # Prepare a response message for the found links
        response_msg = ""
        for i, link in enumerate(all_links, start=1):
            text = link.text.strip()
            hyperlink = link["href"]
            response_msg += f'{i}. [{text}]({hyperlink})\n'
        message.reply_text(response_msg, disable_web_page_preview=True)


# Define the process_link function
def process_link(playwright: Playwright, link: str, message: Message) -> str:
    try:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(link)
        page.locator("#soralink-human-verif-main").click()
        page.locator("#generater").click()
        with page.expect_popup() as page1_info:
            page.locator("#showlink").click()
        page1 = page1_info.value
        final_link = page1.url

        # Close the browser and context
        context.close()
        browser.close()

        return final_link
    except Exception as e:
        # Close the browser and context
        try:
            context.close()
        except:
            pass

        try:
            browser.close()
        except:
            pass

        # Raise the exception to handle it in the mkv_command function
        raise e

# Define the mkv_command function
@app.on_message(filters.command("mkv"))
def mkv_command(client: Client, message: Message):
    try:
        # Get the link from the message text
        link = message.text.split(" ")[1]

        # Check if the link contains "mkvcinemas"
        if "mkvcinemas" not in link:
            message.reply_text("Invalid link. Link must be of 'mkvcinemas.com'.")
            return

        # Send processing message
        process_message = message.reply_text("Processing link, please wait...", quote=True)

        with sync_playwright() as playwright:
            final_link = process_link(playwright, link, message)

        # Edit the process message with the final link
        process_message.edit_text(f"Link processed successfully! \n{final_link}", disable_web_page_preview=True)
    except IndexError:
        # When no link is provided in the message
        message.reply_text("Please provide a valid link after the command. For example, `/mkv https://example.com`", quote=True)
    except Exception as e:
        # When an error occurs during the processing of the link
        message.reply_text(f"An error occurred while processing the link: {e}", quote=True)


# Define the mkv_command function
@app.on_message(filters.command("mkva"))
def mkvcinemas(client: Client, message: Message):
    try:
        # Get the link from the message text
        link = message.text.split(" ")[1]

        # Check if the link contains "mkvcinemas"
        if "mkvcinemas" not in link:
            message.reply_text("Invalid link. Link must be of 'mkvcinemas.com'.")
            return

        # Send processing message
        process_message = message.reply_text("Processing link, please wait...", quote=True)

        # Use the requests library to get the HTML content of the link
        response = requests.get(link)
        html_content = response.text
    
        # Use BeautifulSoup to parse the HTML content and extract all links from the page
        soup = BeautifulSoup(html_content, "html.parser")
        links = [a["href"] for a in soup.find_all("a", {"class": "gdlink"}, href=True)]
    
        # Create an empty list to store the final links
        final_links = []

        # Loop through the links and process only those that contain "mkvcinemas" in the URL
        for link in links:
            if "mkvcinemas" in link:
                with sync_playwright() as playwright:
                    final_link = process_link(playwright, link, message)
                    # Extract the title of the link and append it to the final link
                    title = soup.find("a", {"href": link, "class": "gdlink"}).text
                    final_link += f" - {title}\n"
                    final_links.append(final_link)

        # Edit the process message with the final links
        final_links_text = "\n".join(final_links)

        # Split the final links into chunks of up to 10 links per message
        links_per_message = 5
        final_links_chunks = [final_links[i:i+links_per_message] for i in range(0, len(final_links), links_per_message)]

        for i, links_chunk in enumerate(final_links_chunks):
            # Send each chunk of links as a separate message
            message_text = f"Links processed successfully! (Part {i+1}/{len(final_links_chunks)}) \n\n" + "\n".join(links_chunk)
            message.reply_text(message_text, disable_web_page_preview=True)

    except IndexError:
        # When no link is provided in the message
        message.reply_text("Please provide a valid link after the command. For example, `/mkv https://example.com`", quote=True)
    except Exception as e:
        # When an error occurs during the processing of the link
        message.reply_text(f"An error occurred while processing the link: {e}", quote=True)


# Start the bot
app.run()
