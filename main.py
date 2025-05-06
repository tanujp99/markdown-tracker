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

# --- Configuration ---
load_dotenv()  # Load environment variables from .env file
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SAVE_PATH = os.getenv("MARKDOWN_SAVE_PATH")

# --- Input Validation ---
if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY not found. Please set it in the .env file.")
    exit()
if not SAVE_PATH:
    print("Error: MARKDOWN_SAVE_PATH not found in .env file or environment.")
    print("Please ensure it is defined correctly in the .env file.")
    exit()

# --- Remote LLM Configuration ---
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"Error configuring Remote LLM API: {e}")
    exit()

# Limit text sent to Remote LLM (adjust as needed)
MAX_TEXT_LENGTH_FOR_GEMINI = 15000

# --- Helper Functions ---

def sanitize_filename(name):
    """Removes characters that are invalid for Windows filenames."""
    if not name:
        return "Unnamed Job Posting"
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    name = name[:150] # Limit filename length
    return name if name else "Unnamed Job Posting"

def create_markdown_content(data):
    """Formats the job data into Markdown using the potentially formatted description."""
    description_content = data.get('description', '') # Expects formatted description here

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

# --- Selenium Function ---

def get_page_html_selenium(url):
    """Fetches the full page HTML using Selenium after waiting for JS."""
    print("Initializing Selenium WebDriver...")
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer") 
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=3") # Reduce console noise from Selenium/WebDriver
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    driver = None
    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30) # Set timeout for page load
        print(f"Navigating to {url}...")
        driver.get(url)
        # Simple wait - consider WebDriverWait for more robust waiting if needed
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

# --- Text Extraction Function ---

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

    # List of selectors to try (prioritize more specific ones)
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
                break # Stop after first match
        except Exception as e:
            print(f"Error trying selector '{selector}': {e}")

    # Extract text from the found element OR fallback to body
    target_element = main_content_element if main_content_element else soup.body
    if not main_content_element:
         print("Could not find specific main content element, using text from <body>.")

    if target_element:
        print("Extracting plain text from selected content...")
        # Remove script and style elements before getting text
        for element in target_element(["script", "style"]):
            element.decompose()
        plain_text = target_element.get_text(separator='\n', strip=True)
        plain_text = re.sub(r'\n\s*\n', '\n\n', plain_text) # Clean up whitespace
        print(f"Extracted plain text length: {len(plain_text)} characters.")
    else:
        print("Warning: Could not extract any text content.")
        plain_text = None

    return plain_text

# --- Remote LLM Function (Call 1: Extract Fields + Plain Description) ---

def extract_job_data_with_gemini(text_content, job_url):
    """
    Sends text content to Remote LLM API and asks for structured job data,
    INCLUDING the plain text description.
    """
    if not text_content:
        print("No text content provided to Remote LLM for extraction.")
        return None

    print("Preparing prompt for Remote LLM (extraction call)...")
    limited_text = text_content[:MAX_TEXT_LENGTH_FOR_GEMINI]
    if len(text_content) > MAX_TEXT_LENGTH_FOR_GEMINI:
        print(f"Warning: Text content truncated to {MAX_TEXT_LENGTH_FOR_GEMINI} characters for Remote LLM.")

    prompt = f"""
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
    """

    print("Sending request to Remote LLM API for data extraction...")
    try:
        # Request JSON output format
        generation_config = genai.types.GenerationConfig(response_mime_type="application/json")
        model = genai.GenerativeModel('gemini-1.5-flash', generation_config=generation_config)
        # model = genai.GenerativeModel('gemini-pro', generation_config=generation_config) # Alternative

        response = model.generate_content(prompt)

        # Debugging raw response:
        # print(f"Remote LLM Raw Extraction Response:\n---\n{response.text}\n---")

        # Response should be directly parseable JSON
        extracted_data = json.loads(response.text)
        print("Successfully parsed JSON response from Remote LLM (extraction call).")
        return extracted_data

    except json.JSONDecodeError as e:
        print(f"Error: Failed to decode JSON response from Remote LLM (extraction call): {e}")
        print(f"Remote LLM Raw Response causing error:\n---\n{response.text}\n---")
        return None
    except Exception as e:
        print(f"Error interacting with Remote LLM API (extraction call): {e}")
        # You might want to inspect the response object for more details if it exists
        # if 'response' in locals(): print(f"Full Response Object: {response}")
        return None

# --- Remote LLM Function (Call 2: Format Description) ---

def format_description_with_gemini(plain_description_text):
    """Sends plain text description to Remote LLM API for Markdown formatting."""
    if not plain_description_text:
        print("No description text provided for formatting.")
        return ""

    print("Preparing formatting prompt for Remote LLM...")
    # Limit length again, just in case
    limited_text = plain_description_text[:MAX_TEXT_LENGTH_FOR_GEMINI]
    if len(plain_description_text) > MAX_TEXT_LENGTH_FOR_GEMINI:
         print(f"Warning: Description text truncated to {MAX_TEXT_LENGTH_FOR_GEMINI} characters for formatting.")

    prompt = f"""
Please reformat the following job description using Markdown elements to improve its structure and readability. Use appropriate Markdown for headings (like ## or ### for sections like Responsibilities, Qualifications, About Us, etc.), bold text for emphasis (like **Required Skills:** or **Benefits**), and bullet points (* item or - item) for lists where applicable. Ensure paragraphs are separated by double newlines. Output ONLY the formatted Markdown text. Do not add any introductory sentences, closing remarks, or explanations.

Original Plain Text Description:
---
{limited_text}
---

Formatted Markdown Description:
"""

    print("Sending request to Remote LLM API for formatting...")
    try:
        # For formatting, standard text generation is fine
        model = genai.GenerativeModel('gemini-1.5-flash') # Or 'gemini-pro'
        # Increase temperature slightly for potentially better formatting flow
        generation_config = genai.types.GenerationConfig(temperature=0.3)

        response = model.generate_content(prompt, generation_config=generation_config)
        formatted_text = response.text.strip()
        print("Successfully received formatted description from Remote LLM.")

        # Basic check if formatting likely failed / returned empty or garbage
        if not formatted_text or len(formatted_text) < len(plain_description_text) * 0.5:
             print("Warning: Formatting result seems short or empty. Falling back to plain text.")
             return plain_description_text # Fallback

        return formatted_text
    except Exception as e:
        print(f"Error interacting with Remote LLM API for formatting: {e}")
        print("Falling back to original plain text description.")
        return plain_description_text # Fallback

# --- Main Execution ---

def main():
    print("--- Job Application Markdown Creator ---")
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
            # 3. Extract structured data AND plain description via Remote LLM (Call 1)
            extracted_data = extract_job_data_with_gemini(plain_text_context, job_url)

            if extracted_data:
                # Get the plain description extracted by Remote LLM in the first call
                plain_description = extracted_data.get('description', '').strip()
                if plain_description:
                     # 4. Format the plain description via Remote LLM (Call 2)
                     final_description = format_description_with_gemini(plain_description)
                else:
                     print("Warning: Remote LLM did not return a description in the first call. Using empty description.")
                     final_description = "" # Ensure it's empty if no plain desc found
            else:
                 print("First Remote LLM call failed to extract base data. No description available.")
                 final_description = "Error: Failed to extract job data."
        else:
            print("Could not extract text context for Remote LLM. Cannot proceed.")
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
            'description': final_description.strip(), # Use formatted (or plain fallback) description
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
            # Ensure target directory exists
            os.makedirs(SAVE_PATH, exist_ok=True)
            print(f"Ensured directory exists: {SAVE_PATH}")

            # Generate Markdown content
            markdown_content = create_markdown_content(final_data)
            print("Markdown content generated.")

            # Save the file
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
        print("\nCould not extract base job data automatically using Remote LLM. No file created.")
        # Print the description error if one occurred
        if final_description.startswith("Error:"):
            print(final_description)


if __name__ == "__main__":
    main()