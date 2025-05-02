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
from openai import OpenAI # Import OpenAI library
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()  # Load environment variables from .env file

# --- Local LLM Configuration ---
# Point to your LM Studio server endpoint
LOCAL_LLM_BASE_URL = s.getenv("LOCAL_LLM_BASE_URL")
# LM Studio may not require an API key, use "not-needed" or check LM Studio settings
LOCAL_LLM_API_KEY = "not-needed"
# Specify the model identifier if needed (check LM Studio), otherwise it might use the loaded one
# LOCAL_LLM_MODEL = "loaded-model-name" # Optional: If you want to target a specific served model

# --- Save Path Configuration ---
SAVE_PATH = os.getenv("MARKDOWN_SAVE_PATH") # Use the corrected env var name
if not SAVE_PATH:
    print("Error: MARKDOWN_SAVE_PATH not found in .env file or environment.")
    print("Please ensure it is defined correctly in the .env file.")
    exit()

# Consider limiting text sent to LLM (adjust as needed for local model performance/context window)
MAX_TEXT_LENGTH_FOR_LLM = 15000 # Adjust based on your local model's context capability

# --- Initialize OpenAI Client for Local LLM ---
try:
    client = OpenAI(base_url=LOCAL_LLM_BASE_URL, api_key=LOCAL_LLM_API_KEY)
except Exception as e:
    print(f"Error initializing OpenAI client for local LLM: {e}")
    print("Ensure LM Studio is running and the base URL is correct.")
    exit()

# --- Helper Functions (sanitize_filename, create_markdown_content - remain the same) ---

def sanitize_filename(name):
    """Removes characters that are invalid for Windows filenames."""
    if not name: # Handle cases where name might be None or empty
        return "Unnamed Job Posting"
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    name = name[:150] # Limit filename length reasonably
    return name if name else "Unnamed Job Posting" # Ensure non-empty filename

def create_markdown_content(data):
    """Formats the job data into Markdown based on user's examples."""
    # Using the potentially formatted description now
    description_content = data.get('description', '')

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
    # Ensure consistent line endings
    return content.replace('\r\n', '\n')


# --- Selenium Function (get_page_html_selenium - remains the same) ---

def get_page_html_selenium(url):
    """Fetches the full page HTML using Selenium after waiting for JS."""
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
        time.sleep(5) # Simple wait for dynamic content
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

# --- Text Extraction Function (extract_relevant_text - remains the same) ---

def extract_relevant_text(html_content):
    """Extracts meaningful text content from HTML, trying common tags."""
    if not html_content:
        return None
    print("Parsing HTML with BeautifulSoup...")
    soup = BeautifulSoup(html_content, 'html.parser')
    main_content = None
    selectors = ['main', 'article', '[role="main"]', '#content', '#job-details',
                 '#jobDescriptionText', '.job-description', '.job-details', '.content']
    for selector in selectors:
        try:
            main_content = soup.select_one(selector)
            if main_content:
                print(f"Found main content using selector: '{selector}'")
                break
        except Exception as e:
            print(f"Error trying selector '{selector}': {e}")
    if not main_content:
        print("Could not find specific main content tag, falling back to body.")
        main_content = soup.body
    if main_content:
        print("Extracting text from selected content...")
        text = main_content.get_text(separator='\n', strip=True)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        print(f"Extracted text length: {len(text)} characters.")
        return text
    else:
        print("Warning: Could not extract text content.")
        return None

# --- Local LLM Functions ---

def extract_job_data_with_local_llm(text_content, job_url):
    """Sends text content to Local LLM API and asks for structured job data."""
    if not text_content:
        print("No text content provided to Local LLM for extraction.")
        return None

    print("Preparing extraction prompt for Local LLM...")
    limited_text = text_content[:MAX_TEXT_LENGTH_FOR_LLM]
    if len(text_content) > MAX_TEXT_LENGTH_FOR_LLM:
        print(f"Warning: Text content truncated to {MAX_TEXT_LENGTH_FOR_LLM} characters for Local LLM.")

    messages = [
        {"role": "system", "content": "You are a helpful assistant designed to extract specific information from job postings and output it ONLY as a valid JSON object."},
        {"role": "user", "content": f"""
Analyze the following job posting text obtained from the URL "{job_url}".
Extract the specific information requested below.
Provide the output ONLY as a single valid JSON object with the following exact keys:
- "company": The name of the hiring company.
- "role": The specific job title or role.
- "location": The primary location(s) mentioned (e.g., "Chicago, IL", "Remote", "London, UK").
- "comp": The salary or compensation range if explicitly mentioned (e.g., "$100,000 - $120,000", "£50k"). Otherwise, "".
- "req": The requisition ID or job ID if explicitly mentioned. Otherwise, "".
- "description": The main body of the job description, duties, and qualifications as plain text. Preserve paragraph breaks with newline characters (\\n).

If any piece of information is not found or cannot be determined, use an empty string "" for its value. Do not add any introductory text, explanations, or markdown formatting around the JSON object.

Job Posting Text:
---
{limited_text}
---

JSON Output:
"""}
    ]

    print("Sending extraction request to Local LLM API...")
    try:
        response = client.chat.completions.create(
            model="loaded-model-name", # Use LM Studio's loaded model, or specify if needed
            messages=messages,
            temperature=0.1, # Lower temperature for more deterministic JSON output
            response_format={"type": "json_object"} # Request JSON mode if supported by model/endpoint
        )

        # Debug: Print raw response content
        # raw_response_content = response.choices[0].message.content
        # print(f"LLM Raw Response Content:\n---\n{raw_response_content}\n---")

        # Attempt to parse the JSON response
        extracted_data = json.loads(response.choices[0].message.content)
        print("Successfully parsed JSON response from Local LLM.")
        return extracted_data

    except json.JSONDecodeError as e:
        print(f"Error: Failed to decode JSON response from Local LLM: {e}")
        raw_content = response.choices[0].message.content if response and response.choices else "No response content"
        print(f"LLM Raw Response causing error:\n---\n{raw_content}\n---")
        return None
    except Exception as e:
        print(f"Error interacting with Local LLM API for extraction: {e}")
        return None

def format_description_with_llm(description_text):
    """Sends plain text description to Local LLM for Markdown formatting."""
    if not description_text:
        print("No description text provided for formatting.")
        return "" # Return empty string if no input

    print("Preparing formatting prompt for Local LLM...")
    messages = [
        {"role": "system", "content": "You are a helpful assistant designed to format job descriptions using Markdown for better readability. Use headings (##, ###), bolding (**text**), and bullet points (* item) appropriately. Do not add any commentary before or after the formatted text."},
        {"role": "user", "content": f"""
Please reformat the following job description using Markdown elements (like ## headings for sections, **bold** for emphasis on key terms or subheadings, and * bullet points for lists) to improve its structure and readability. Output only the formatted Markdown text.

Original Description:
---
{description_text}
---

Formatted Markdown Description:
"""}
    ]

    print("Sending formatting request to Local LLM API...")
    try:
        response = client.chat.completions.create(
            model="loaded-model-name", # Use LM Studio's loaded model
            messages=messages,
            temperature=0.5, # Allow some creativity in formatting
        )
        formatted_text = response.choices[0].message.content.strip()
        print("Successfully received formatted description from Local LLM.")
        return formatted_text
    except Exception as e:
        print(f"Error interacting with Local LLM API for formatting: {e}")
        # Fallback to original text if formatting fails
        print("Falling back to original description text.")
        return description_text


# --- Main Execution ---

def main():
    print("--- Job Application Markdown Creator (Selenium + Local LLM) ---")
    job_url = input("1. Paste the Job Application URL: ")

    # 1. Fetch HTML using Selenium
    html_content = get_page_html_selenium(job_url)

    extracted_data = None
    plain_description = ""
    if html_content:
        # 2. Extract relevant text using BeautifulSoup
        text_content = extract_relevant_text(html_content)

        if text_content:
            # 3. Extract structured data using Local LLM
            extracted_data = extract_job_data_with_local_llm(text_content, job_url)
            if extracted_data:
                plain_description = extracted_data.get('description', '') # Store plain description
        else:
            print("Skipping LLM step as no relevant text could be extracted.")
    else:
        print("Skipping further steps as page HTML could not be fetched.")


    # 4. Format Description and Save Markdown File
    if extracted_data and plain_description:
        print("Attempting to format description using Local LLM...")
        # 4a. Format the description using another LLM call
        formatted_description = format_description_with_llm(plain_description)

        print("Extraction and formatting successful. Preparing Markdown file...")

        # Prepare final data dictionary, using the formatted description
        final_data = {
            'company': extracted_data.get('company', '').strip(),
            'role': extracted_data.get('role', '').strip(),
            'location': extracted_data.get('location', '').strip(),
            'comp': extracted_data.get('comp', '').strip(),
            'req': extracted_data.get('req', '').strip(),
            'description': formatted_description, # Use the formatted version
            'link': job_url,
            'date_applied': datetime.date.today().strftime('%Y-%m-%d'),
            # Defaults below
            'applied': True,
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

    elif extracted_data and not plain_description:
         print("\nExtracted data but no description found to format. Saving with plain data.")
         # Code to save with plain description if formatting wasn't possible but extraction worked
         # (Similar to saving block above, but ensure final_data['description'] is the plain one)

    else:
        print("\nCould not automatically extract job data using Local LLM.")


if __name__ == "__main__":
    main()