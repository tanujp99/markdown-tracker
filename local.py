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
from openai import OpenAI # Use OpenAI library for local endpoint
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()  # Load environment variables from .env file

# --- Local LLM Configuration ---
LOCAL_LLM_BASE_URL = os.getenv("LOCAL_LLM_BASE_URL")
LOCAL_LLM_API_KEY = "not-needed" # LM Studio typically doesn't require a key
# Optional: Specify model if your server hosts multiple, otherwise it uses the loaded one
# LOCAL_LLM_MODEL_NAME = "lmstudio-community/Meta-Llama-3-8B-Instruct-GGUF" # Example

# --- Save Path Configuration ---
SAVE_PATH = os.getenv("MARKDOWN_SAVE_PATH")
if not SAVE_PATH:
    print("Error: MARKDOWN_SAVE_PATH not found in .env file or environment.")
    print("Please ensure it is defined correctly in the .env file.")
    exit()

# Limit text sent to LLM (adjust based on your local model's context capability)
MAX_TEXT_LENGTH_FOR_LLM = 64000 # Adjust lower/higher based on model and performance

# --- Initialize OpenAI Client for Local LLM ---
try:
    client = OpenAI(base_url=LOCAL_LLM_BASE_URL, api_key=LOCAL_LLM_API_KEY)
    print(f"OpenAI client initialized for local LLM at {LOCAL_LLM_BASE_URL}")
except Exception as e:
    print(f"Error initializing OpenAI client for local LLM: {e}")
    print("Ensure LM Studio is running and the base URL is correct.")
    exit()

# --- Helper Functions (sanitize_filename, create_markdown_content - same as Gemini version) ---

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
    return content.replace('\r\n', '\n')

# --- Selenium Function (get_page_html_selenium - same as Gemini version) ---

def get_page_html_selenium(url):
    """Fetches the full page HTML using Selenium after waiting for JS."""
    print("Initializing Selenium WebDriver...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu") # You already have this
    options.add_argument("--disable-software-rasterizer") # Try adding this
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=3") # Reduces general Selenium/driver logs
    # Suppress specific DevTools logging messages (might hide the GPU errors)
    options.add_experimental_option('excludeSwitches', ['enable-logging'])

    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    driver = None
    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)
        print(f"Navigating to {url}...")
        driver.get(url)
        print("Waiting briefly for dynamic content...")
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

# --- Text Extraction Function (extract_plain_description_text - same as two-call Gemini version) ---

def extract_plain_description_text(html_content):
    """
    Attempts to find the main job description block and returns its plain text.
    Falls back to body text if specific selectors fail.
    """
    if not html_content:
        return None
    print("Parsing HTML with BeautifulSoup...")
    soup = BeautifulSoup(html_content, 'html.parser')
    main_content_element = None
    plain_text = None
    selectors = [
        '#jobDescriptionText', '.job-description', '.job-details', '#job-details',
        'article', '[role="main"]', 'main', '#content', '.content'
    ]
    print(f"Trying selectors: {selectors}")
    for selector in selectors:
        try:
            main_content_element = soup.select_one(selector)
            if main_content_element:
                print(f"Found potential content element using selector: '{selector}'")
                break
        except Exception as e:
            print(f"Error trying selector '{selector}': {e}")

    target_element = main_content_element if main_content_element else soup.body
    if not main_content_element:
         print("Could not find specific main content element, using text from <body>.")

    if target_element:
        print("Extracting plain text from selected content...")
        for element in target_element(["script", "style"]):
            element.decompose()
        plain_text = target_element.get_text(separator='\n', strip=True)
        plain_text = re.sub(r'\n\s*\n', '\n\n', plain_text)
        print(f"Extracted plain text length: {len(plain_text)} characters.")
    else:
        print("Warning: Could not extract any text content.")
        plain_text = None
    return plain_text

# --- Local LLM Function (Call 1: Extract Fields + Plain Description) ---

def extract_job_data_with_local_llm(text_content, job_url):
    """
    Sends text content to Local LLM API and asks for structured job data,
    INCLUDING the plain text description. Uses OpenAI library format.
    """
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

If any piece of information is not found or cannot be determined, use an empty string "" for its value. Ensure the entire output is a single, valid JSON object starting with {{ and ending with }}.

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
            # model=LOCAL_LLM_MODEL_NAME, # Optional: Specify model if needed
            model="loaded-model-name", # Tells LM Studio to use the currently loaded model
            messages=messages,
            temperature=0.1, # Low temp for reliable JSON
            # Request JSON mode if supported by model/endpoint (experimental)
            # response_format={"type": "json_object"}
        )

        response_content = response.choices[0].message.content
        # Debugging raw response:
        # print(f"Local LLM Raw Extraction Response:\n---\n{response_content}\n---")

        # Clean potential markdown code block fences around JSON
        json_string = response_content.strip().lstrip('```json').rstrip('```').strip()
        if not json_string:
            print("Error: Local LLM returned empty content for extraction.")
            return None

        extracted_data = json.loads(json_string)
        print("Successfully parsed JSON response from Local LLM (extraction call).")
        return extracted_data

    except json.JSONDecodeError as e:
        print(f"Error: Failed to decode JSON response from Local LLM (extraction call): {e}")
        response_content = response.choices[0].message.content if response and response.choices else "No response content"
        print(f"LLM Raw Response causing error:\n---\n{response_content}\n---")
        return None
    except Exception as e:
        print(f"Error interacting with Local LLM API (extraction call): {e}")
        return None

# --- Local LLM Function (Call 2: Format Description) ---

def format_description_with_local_llm(plain_description_text):
    """Sends plain text description to Local LLM API for Markdown formatting."""
    if not plain_description_text:
        print("No description text provided for formatting.")
        return ""

    print("Preparing formatting prompt for Local LLM...")
    limited_text = plain_description_text[:MAX_TEXT_LENGTH_FOR_LLM]
    if len(plain_description_text) > MAX_TEXT_LENGTH_FOR_LLM:
         print(f"Warning: Description text truncated to {MAX_TEXT_LENGTH_FOR_LLM} characters for formatting.")

    messages = [
        {"role": "system", "content": "You are a helpful assistant skilled at formatting text using Markdown. Given a plain text job description, reformat it using Markdown elements like headings (##, ###), bold (**text**), and lists (* or -) to improve readability and structure. Output only the formatted Markdown, with no extra explanation."},
        {"role": "user", "content": f"""
Please reformat the following job description using Markdown elements to improve its structure and readability. Use appropriate Markdown for headings (like ## or ### for sections like Responsibilities, Qualifications, About Us, etc.), bold text for emphasis (like **Required Skills:** or **Benefits**), and bullet points (* item or - item) for lists where applicable. Ensure paragraphs are separated by double newlines. Output ONLY the formatted Markdown text.

Original Plain Text Description:
---
{limited_text}
---

Formatted Markdown Description:
"""}
    ]

    print("Sending formatting request to Local LLM API...")
    try:
        response = client.chat.completions.create(
            # model=LOCAL_LLM_MODEL_NAME, # Optional: Specify model if needed
            model="loaded-model-name", # Use LM Studio's loaded model
            messages=messages,
            temperature=0.4, # Slightly higher temp for formatting
        )
        formatted_text = response.choices[0].message.content.strip()
        print("Successfully received formatted description from Local LLM.")

        # Basic check for empty/failed formatting
        if not formatted_text or len(formatted_text) < len(plain_description_text) * 0.5:
             print("Warning: Formatting result seems short or empty. Falling back to plain text.")
             return plain_description_text
        return formatted_text
    except Exception as e:
        print(f"Error interacting with Local LLM API for formatting: {e}")
        print("Falling back to original plain text description.")
        return plain_description_text # Fallback

# --- Main Execution ---

def main():
    print("--- Job Application Markdown Creator (Selenium + Local LLM: 2-Call Format) ---")
    job_url = input("- Paste the Job Application URL: ")

    # 1. Fetch HTML using Selenium
    html_content = get_page_html_selenium(job_url)

    extracted_data = None
    plain_description = ""     # Store plain description from first call
    final_description = ""     # Store final description (formatted or plain)

    if html_content:
        # 2. Extract plain text content (best effort)
        plain_text_context = extract_plain_description_text(html_content)

        if plain_text_context:
            # 3. Extract structured data AND plain description via Local LLM (Call 1)
            extracted_data = extract_job_data_with_local_llm(plain_text_context, job_url)

            if extracted_data:
                # Get the plain description extracted by the LLM
                plain_description = extracted_data.get('description', '').strip()
                if plain_description:
                     # 4. Format the plain description via Local LLM (Call 2)
                     final_description = format_description_with_local_llm(plain_description)
                else:
                     print("Warning: Local LLM did not return a description in the first call. Using empty description.")
                     final_description = ""
            else:
                 print("First Local LLM call failed to extract base data. No description available.")
                 final_description = "Error: Failed to extract job data."
        else:
            print("Could not extract text context for Local LLM. Cannot proceed.")
            final_description = "Error: Could not extract page text."
    else:
        print("Skipping further steps as page HTML could not be fetched.")
        final_description = "Error: Could not fetch page HTML."

    # 5. Process and Save Markdown File (Only if base data extraction was successful)
    if extracted_data:
        print("Base data extraction successful. Preparing Markdown file...")

        # Prepare final data dictionary
        final_data = {
            'company': extracted_data.get('company', '').strip(),
            'role': extracted_data.get('role', '').strip(),
            'location': extracted_data.get('location', '').strip(),
            'comp': extracted_data.get('comp', '').strip(),
            'req': extracted_data.get('req', '').strip(),
            'description': final_description.strip(), # Use formatted or plain fallback
            'link': job_url,
            'date_applied': datetime.date.today().strftime('%Y-%m-%d'),
            'applied': True, # Defaults
            'recruiter_screen': '',
            'interview': False,
            'rejection': False,
            'declined': False,
        }

        # --- Filename Generation, Directory Creation, Saving ---
        company_name = final_data.get('company')
        role_name = final_data.get('role')
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

        try:
            os.makedirs(SAVE_PATH, exist_ok=True)
            print(f"Ensured directory exists: {SAVE_PATH}")
            markdown_content = create_markdown_content(final_data)
            print("Markdown content generated.")
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            print("-" * 30)
            print(f"Successfully created Markdown file:")
            print(f"{full_path}")
            print("-" * 30)
        except OSError as e:
            print(f"\nError creating directory or writing file {full_path}: {e}")
        except IOError as e:
            print(f"\nError writing file {full_path}: {e}")
        except Exception as e:
            print(f"\nAn unexpected error occurred during file processing: {e}")

    else:
        print("\nCould not extract base job data automatically using Local LLM. No file created.")
        if final_description.startswith("Error:"):
            print(final_description)

if __name__ == "__main__":
    main()