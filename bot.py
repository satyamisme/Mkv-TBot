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
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
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

def scrape(query, index=0):
    # Construct the URL for the search query
    url = f"{MKV_DOMAIN}/?s={query}"
    response = requests.get(url)

    # Parse the HTML content of the website using BeautifulSoup
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find the first element that has both "ml-mask" and "jt" as its class attributes
    elems = soup.find_all(class_=["ml-mask", "jt"])
    
    # Extract the href, title, and thumbnail attributes from the first element
    for loop, elem in enumerate(elems):
        if index == loop:
            href = elem.get('href')
            title = elem.get('oldtitle')
            if href:
                resp = requests.get(href)
                nsoup = BeautifulSoup(resp.content, 'html.parser')
                thumb = nsoup.find('meta', {'property': 'og:image'})
                thumbnail = thumb['content'] if thumb else None

            # Return a dictionary containing the href, title, and thumbnail
            if title and href:
                return {'href': href, 'title': title, 'thumbnail': thumbnail, 'posts': len(elems)}
    return None

@app.on_message(filters.command('search'))
async def search(client: Client, message: Message):
    # Get the search query from the message text and replace spaces with '+'
    try:
        query = message.text.split(' ', 1)[1].replace(' ', '+')
    except IndexError:
        await message.reply_text("Please provide a search query.")
        return

    # Generate Wait Msg
    msg = await message.reply_text("Searching...")

    # Scrape the website for the first search result
    search_result = scrape(query)

    # Generate a Custom Keyboard
    reply_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⌫", callback_data=f"search pre 0 {query}"), InlineKeyboardButton(f"ᴘᴏsᴛs\n1 / {search_result['posts']}", callback_data=f"search posts 0 {query}"), InlineKeyboardButton("⌦", callback_data=f"search nex 0 {query}")]])

    # Send the search result as a reply to the user
    if search_result:
        await post_result(message, msg, search_result, reply_keyboard)
    else:
        await msg.edit("No search results found.")

async def post_result(m: Message, msg, search_result, reply_keyboard, edit=False):
    caption = f"<b>Title :</b> <i>{search_result['title']}</i>\n\n<b>Link :</b> {search_result['href']}"
    if search_result['thumbnail']:
        # Check if the "thumbnails" directory exists and create it if it doesn't
        if not os.path.exists("thumbnails"):
            os.makedirs("thumbnails")
        # Download the image from the URL using requests
        image_url = search_result['thumbnail'].replace("w300", "w1280")
        response = requests.get(image_url)
        image_data = response.content
        # Save the image as a thumbnail in a folder called "thumbnails"
        thumbnail_filename = os.path.basename(image_url)
        thumbnail_path = os.path.join("thumbnails", thumbnail_filename)
        with open(thumbnail_path, "wb") as f:
            f.write(image_data)
        # Send the thumbnail with the caption to the chat
        if msg:
            await msg.delete()
        if edit:
            await m.edit_media(InputMediaPhoto(media="https://i.imgur.com/arOB1y2.jpg", caption=caption), reply_markup=reply_keyboard)
        else:
            await m.reply_photo(photo=thumbnail_path, caption=caption, reply_markup=reply_keyboard)
        os.remove(thumbnail_path)
    else:
        await msg.edit(caption, disable_web_page_preview=True, reply_markup=reply_keyboard)

@app.on_callback_query(filters.regex('^search'))
async def cb_handler(c: Client, cb: CallbackQuery):
    qdata = cb.data.split()
    if qdata[1] == "pre":
        qdata[2] = int(qdata[2])
        qdata[2] -= 1
    elif qdata[1] == "nex":
        qdata[2] = int(qdata[2])
        qdata[2] += 1
    elif qdata[1] == "posts":
        await cb.answer()
        return
    result = scrape(qdata[3], qdata[2])
    reply_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⌫", callback_data=f"search pre {qdata[2]} {qdata[3]}"), InlineKeyboardButton(f"ᴘᴏsᴛs\n{qdata[2]+1} / {result['posts']}", callback_data=f"search posts {qdata[2]} {qdata[3]}"), InlineKeyboardButton("⌦", callback_data=f"search nex {qdata[2]} {qdata[3]}")]])
    await post_result(cb.message, None, result, reply_keyboard, True)
    await cb.answer()

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

# Regex patterns to extract resolution and format
res_pattern = re.compile(r"\b(\d+p)\b")
fmt_pattern = re.compile(r"\b(HEVC|10-bit|Web-DL|NF)\b")


@app.on_message(filters.command("links"))
async def get_links(client, message):
    # Get the URL from the command message
    url = message.text.split()[1]

    try:
        response = requests.get(url)
        html = response.content
        soup = BeautifulSoup(html, "html.parser")

        # Initialize dictionaries to hold movies by resolution and format
        resolutions = {"480p": [], "720p": [], "1080p": []}
        formats = {"HEVC": [], "10-bit": [], "Web-DL": [], "NF": []}

        # Find all elements with download links
        for link in soup.find_all("a", href=True):
            href = link.get("href")
            title = link.get_text()

            # Check if the link contains "https://ww3.mkvcinemas.lat" and has the class of gdlink
            if "https://ww3.mkvcinemas.lat?" in href and "gdlink" in link.get("class"):
                # Extract the resolution and format from the title using regex
                resolution = res_pattern.search(title)
                format_ = fmt_pattern.search(title)

                # Categorize the movie by resolution and format
                if resolution and format_:
                    resolution = resolution.group(1)
                    format_ = format_.group(1)
                    category = f"{resolution} {format_}"
                    resolutions.setdefault(category, []).append((href, title))
                elif resolution:
                    resolution = resolution.group(1)
                    resolutions.setdefault(resolution, []).append((href, title))

        # Send the movies grouped by category
        serial_number = 1
        for cat, movies in resolutions.items():
            if movies:
                # Create a list of all movie hyperlinks for this category
                movie_links = [f"{serial_number}. [{movie[1]}]({movie[0]})" for movie in movies]
                serial_number += 1
                # Join the list of movie hyperlinks with newlines
                movie_links_str = "\n".join(movie_links)
                # Send the category name and all movie hyperlinks in a single message
                await message.reply(f"{cat}:\n{movie_links_str}", disable_web_page_preview=True)
            else:
                # If there are no category-wise movies, add the resolution-wise links to a list
                resolution = cat.split()[0]
                links = [f"{serial_number}. [{title}]({href})" for link in soup.find_all("a", href=True)
                         if resolution in link.get_text() and
                         "https://ww3.mkvcinemas.lat?" in link.get("href") and
                         "gdlink" in link.get("class") and
                         not fmt_pattern.search(link.get_text())]
                # Send all resolution-wise links in a single message
                if links:
                    await message.reply(f"{resolution}:\n" + "\n".join(links), disable_web_page_preview=True)

    except Exception as e:
        await message.reply(f"Error: {str(e)}")


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
