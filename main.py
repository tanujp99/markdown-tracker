import os
import datetime
import re
import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException
from bs4 import BeautifulSoup
import google.generativeai as genai
from dotenv import load_dotenv
from markdownify import markdownify # Import markdownify

# --- Configuration ---
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY not found. Please set it in the .env file.")
    exit()

genai.configure(api_key=GEMINI_API_KEY)
SAVE_PATH = os.getenv("MARKDOWN_SAVE_PATH") # Use the corrected env var name
if not SAVE_PATH:
    print("Error: MARKDOWN_SAVE_PATH not found in .env file or environment.")
    exit()

MAX_TEXT_LENGTH_FOR_GEMINI = 15000

# --- Helper Functions (sanitize_filename - same, create_markdown_content - uses formatted desc) ---

def sanitize_filename(name):
    """Removes characters that are invalid for Windows filenames."""
    if not name:
        return "Unnamed Job Posting"
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    name = name[:150]
    return name if name else "Unnamed Job Posting"

def create_markdown_content(data):
    """Formats the job data into Markdown using the potentially formatted description."""
    description_content = data.get('description', '') # This will now be Markdown

    content = f"""---
company: {data.get('company', '')}
tags:
  - jobpost
role: {data.get('role', '')}
location: {data.get('location', '')}
applied: true
date_applied: {data.get('date_applied', '')}
recruiter_screen: ''
interview: false
rejection: false
declined: false
comp: {data.get('comp', '')}
req: {data.get('req', '')}
link: {data.get('link', '')}
---

## Description

{description_content}
"""
    return content.replace('\r\n', '\n')


# --- Selenium Function (get_page_html_selenium - same) ---
def get_page_html_selenium(url):
    # ... (Keep the existing Selenium function exactly the same) ...
    print("Initializing Selenium WebDriver...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    driver = None
    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print(f"Navigating to {url}...")
        driver.get(url)
        time.sleep(5)
        print("Retrieving page source...")
        html_content = driver.page_source
        print("Page source retrieved successfully.")
        return html_content
    except WebDriverException as e:
        print(f"Selenium error navigating to {url}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during Selenium operation: {e}")
        return None
    finally:
        if driver:
            print("Closing Selenium WebDriver.")
            driver.quit()


# --- Text/HTML Extraction Function (Modified) ---
def extract_content_parts(html_content):
    """
    Extracts both the relevant BeautifulSoup element for formatting
    and the plain text for Gemini context.
    Returns: (BeautifulSoup Element | None, str | None)
    """
    if not html_content:
        return None, None

    print("Parsing HTML with BeautifulSoup...")
    soup = BeautifulSoup(html_content, 'html.parser')
    main_content_element = None
    main_content_text = None

    # Try to find common main content containers - This is heuristic!
    selectors = ['main', 'article', '[role="main"]', '#content', '#job-details',
                 '#jobDescriptionText', '.job-description', '.job-details', '.content']
    for selector in selectors:
        try:
            main_content_element = soup.select_one(selector)
            if main_content_element:
                print(f"Found main content element using selector: '{selector}'")
                break
        except Exception as e:
            print(f"Error trying selector '{selector}': {e}")

    if not main_content_element:
        print("Could not find specific main content tag, falling back to body.")
        main_content_element = soup.body

    if main_content_element:
        print("Extracting plain text from selected content...")
        # Get the plain text version for Gemini context
        main_content_text = main_content_element.get_text(separator='\n', strip=True)
        main_content_text = re.sub(r'\n\s*\n', '\n\n', main_content_text)
        print(f"Extracted text length for Gemini: {len(main_content_text)} characters.")
    else:
        print("Warning: Could not extract content element.")
        main_content_element = None # Ensure it's None if body wasn't found either

    # Return the BeautifulSoup element itself and the plain text
    return main_content_element, main_content_text

# --- Gemini Function (Modified Prompt) ---

def extract_job_data_with_gemini(text_content, job_url):
    """
    Sends text content to Gemini API and asks for structured job data,
    *excluding* the description (as we'll format that separately).
    """
    if not text_content:
        print("No text content provided to Gemini.")
        return None

    print("Preparing prompt for Gemini (excluding description field)...")
    limited_text = text_content[:MAX_TEXT_LENGTH_FOR_GEMINI]
    if len(text_content) > MAX_TEXT_LENGTH_FOR_GEMINI:
        print(f"Warning: Text content truncated to {MAX_TEXT_LENGTH_FOR_GEMINI} characters for Gemini.")

    # Modified prompt: Ask for description as "" or omit it
    prompt = f"""
    Analyze the following job posting text obtained from the URL "{job_url}".
    Extract the specific information requested below.
    Provide the output ONLY as a single valid JSON object with the following exact keys:
    - "company": The name of the hiring company.
    - "role": The specific job title or role.
    - "location": The primary location(s) mentioned (e.g., "Chicago, IL", "Remote", "London, UK").
    - "comp": The salary or compensation range if explicitly mentioned (e.g., "$100,000 - $120,000", "£50k"). Otherwise, "".
    - "req": The requisition ID or job ID if explicitly mentioned. Otherwise, "".

    If any piece of information is not found or cannot be determined, use an empty string "" for its value. Do not include a "description" key in the JSON.

    Job Posting Text:
    ---
    {limited_text}
    ---

    JSON Output:
    """

    print("Sending request to Gemini API...")
    try:
        # Ensure JSON mode is requested if available and desired for reliability
        generation_config = genai.types.GenerationConfig(response_mime_type="application/json")
        model = genai.GenerativeModel('gemini-1.5-flash', generation_config=generation_config)
        # Or use 'gemini-pro' if flash is not sufficient
        # model = genai.GenerativeModel('gemini-pro', generation_config=generation_config)

        response = model.generate_content(prompt)

        # Debug: Print raw response
        # print(f"Gemini Raw Response Text:\n---\n{response.text}\n---")

        # The response should directly be parseable JSON if response_mime_type worked
        extracted_data = json.loads(response.text)
        print("Successfully parsed JSON response from Gemini.")
        return extracted_data

    except json.JSONDecodeError as e:
        print(f"Error: Failed to decode JSON response from Gemini: {e}")
        print(f"Gemini Raw Response causing error:\n---\n{response.text}\n---")
        return None
    except Exception as e:
        print(f"Error interacting with Gemini API: {e}")
        # print(f"Full Gemini Response Object: {response}")
        return None

# --- Main Execution (Modified) ---

# --- Main Execution (Modified) ---

def main():
    print("--- Job Application Markdown Creator (Selenium + Gemini w/ Formatting, No Images) ---")
    job_url = input("1. Paste the Job Application URL: ")

    # 1. Fetch HTML using Selenium
    html_content = get_page_html_selenium(job_url)

    extracted_data = None
    formatted_description = "" # Initialize formatted description

    if html_content:
        # 2. Extract relevant BeautifulSoup element and plain text
        # Now gets the BS4 element directly
        main_content_element, main_text_content = extract_content_parts(html_content)

        if main_text_content:
            # 3. Extract structured data (excluding desc) using Gemini
            extracted_data = extract_job_data_with_gemini(main_text_content, job_url)

        # 4. Remove images and Convert HTML element to Markdown LOCALLY
        if main_content_element:
            print("Removing images from HTML fragment...")
            try:
                # Find all 'img' tags within the extracted element and remove them
                for img_tag in main_content_element.find_all('img'):
                    img_tag.decompose() # Removes the tag and its content

                print("Converting image-free HTML fragment to Markdown...")
                # Convert the *modified* element back to string for markdownify
                html_no_images = str(main_content_element)
                formatted_description = markdownify(html_no_images, heading_style="ATX")
                print("HTML successfully converted to Markdown (no images).")

            except Exception as e:
                print(f"Error during image removal or Markdown conversion: {e}")
                print("Falling back to plain text description if available.")
                formatted_description = main_text_content # Fallback to plain text
        elif main_text_content:
             print("Warning: No HTML element found for formatting, using plain text.")
             formatted_description = main_text_content
        else:
            print("Skipping formatting as no relevant content could be extracted.")

    else:
        print("Skipping further steps as page HTML could not be fetched.")


    # 5. Process and Save Markdown File (This part remains the same)
    if extracted_data:
        print("Gemini extraction successful. Preparing Markdown file...")

        # Prepare final data dictionary using the formatted description
        final_data = {
            'company': extracted_data.get('company', '').strip(),
            'role': extracted_data.get('role', '').strip(),
            'location': extracted_data.get('location', '').strip(),
            'comp': extracted_data.get('comp', '').strip(),
            'req': extracted_data.get('req', '').strip(),
            'description': formatted_description.strip(), # Use the formatted/converted MD (now without images)
            'link': job_url,
            'date_applied': datetime.date.today().strftime('%Y-%m-%d'),
            'applied': True, # Defaults
            'recruiter_screen': '',
            'interview': False,
            'rejection': False,
            'declined': False,
        }

        # Create filename
        company_name = final_data.get('company')
        role_name = final_data.get('role')
        # ... (filename generation logic - same as before) ...
        if not company_name and not role_name:
             base_filename = f"Job Posting {final_data['date_applied']}.md"
             print("Warning: Could not determine Company or Role. Using generic filename.")
        elif not company_name:
             base_filename = f"Unknown Company - {role_name}.md"
        elif not role_name:
            base_filename = f"{company_name} - Unknown Role.md"
        else:
            base_filename = f"{company_name} - {role_name}.md"

        safe_filename = sanitize_filename(base_filename)
        full_path = os.path.join(SAVE_PATH, safe_filename)

        # Create directory if needed
        try:
            os.makedirs(SAVE_PATH, exist_ok=True)
        except OSError as e:
            print(f"\nError creating directory {SAVE_PATH}: {e}")
            return

        # Generate Markdown content
        markdown_content = create_markdown_content(final_data)

        # Save the file
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            print("-" * 30)
            print(f"Successfully created Markdown file:")
            print(f"{full_path}")
            print("-" * 30)
        except IOError as e:
            print(f"\nError writing file {full_path}: {e}")
        except Exception as e:
            print(f"\nAn unexpected error occurred during file writing: {e}")

    else:
        print("\nCould not extract base job data automatically using Gemini.")
        if formatted_description:
             print("However, a description fragment was processed (without images). Consider manual entry for other fields.")


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()