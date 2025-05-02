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
if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY not found. Please set it in the .env file.")
    exit()

genai.configure(api_key=GEMINI_API_KEY)
# SAVE_PATH = r"C:\MySpace\journal kenobi\exocortex\Hunt\Post"
SAVE_PATH = os.getenv("MARKDOWN_SAVE_PATH")
# Consider limiting text sent to Gemini API (adjust as needed for cost/performance)
MAX_TEXT_LENGTH_FOR_GEMINI = 15000

# --- Helper Functions ---

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

{data.get('description', '')}
"""
    # Ensure consistent line endings
    return content.replace('\r\n', '\n')

# --- Selenium Function ---

def get_page_html_selenium(url):
    """Fetches the full page HTML using Selenium after waiting for JS."""
    print("Initializing Selenium WebDriver...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Run Chrome in headless mode (no UI)
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36") # Set user agent

    driver = None # Initialize driver to None
    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print(f"Navigating to {url}...")
        driver.get(url)
        # Wait a few seconds for dynamic content to potentially load
        # More advanced waits (WebDriverWait) are better but add complexity.
        time.sleep(5)
        print("Retrieving page source...")
        html_content = driver.page_source # Get source after JS execution
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

def extract_relevant_text(html_content):
    """Extracts meaningful text content from HTML, trying common tags."""
    if not html_content:
        return None

    print("Parsing HTML with BeautifulSoup...")
    soup = BeautifulSoup(html_content, 'html.parser')

    # Try to find common main content containers - This is heuristic!
    main_content = None
    selectors = ['main', 'article', '[role="main"]', '#content', '#job-details',
                 '#jobDescriptionText', '.job-description', '.job-details', '.content'] # Add more common selectors if needed
    for selector in selectors:
        try:
            main_content = soup.select_one(selector)
            if main_content:
                print(f"Found main content using selector: '{selector}'")
                break
        except Exception as e:
            print(f"Error trying selector '{selector}': {e}") # Handle potential invalid selectors

    if not main_content:
        print("Could not find specific main content tag, falling back to body.")
        main_content = soup.body # Fallback to the whole body if specific tags fail

    if main_content:
        print("Extracting text from selected content...")
        # Use .get_text() with a separator for better structure
        text = main_content.get_text(separator='\n', strip=True) #
        # Basic cleaning (optional: more advanced cleaning can be done)
        text = re.sub(r'\n\s*\n', '\n\n', text) # Consolidate multiple newlines
        print(f"Extracted text length: {len(text)} characters.")
        return text
    else:
        print("Warning: Could not extract text content.")
        return None

# --- Gemini Function ---

def extract_job_data_with_gemini(text_content, job_url):
    """Sends text content to Gemini API and asks for structured job data."""
    if not text_content:
        print("No text content provided to Gemini.")
        return None

    print("Preparing prompt for Gemini...")
    # Limit text length to control API cost and avoid potential limits
    limited_text = text_content[:MAX_TEXT_LENGTH_FOR_GEMINI]
    if len(text_content) > MAX_TEXT_LENGTH_FOR_GEMINI:
        print(f"Warning: Text content truncated to {MAX_TEXT_LENGTH_FOR_GEMINI} characters for Gemini.")

    prompt = f"""
    Analyze the following job posting text obtained from the URL "{job_url}".
    Extract the specific information requested below.
    Provide the output ONLY as a single valid JSON object with the following exact keys:
    - "company": The name of the hiring company.
    - "role": The specific job title or role.
    - "location": The primary location(s) mentioned (e.g., "Chicago, IL", "Remote", "London, UK").
    - "comp": The salary or compensation range if explicitly mentioned (e.g., "$100,000 - $120,000", "£50k"). Otherwise, "".
    - "req": The requisition ID or job ID if explicitly mentioned. Otherwise, "".
    - "description": The main body of the job description, duties, and qualifications. Preserve formatting like paragraphs and bullet points where possible using newline characters (\\n).

    If any piece of information is not found or cannot be determined, use an empty string "" for its value. Do not add any introductory text, explanations, or markdown formatting around the JSON object.

    Job Posting Text:
    ---
    {limited_text}
    ---

    JSON Output:
    """

    print("Sending request to Gemini API...")
    try:
        model = genai.GenerativeModel('gemini-1.5-flash') # Or 'gemini-pro' if flash isn't sufficient
        response = model.generate_content(prompt)

        # Debug: Print raw response
        # print(f"Gemini Raw Response Text:\n---\n{response.text}\n---")

        # Attempt to parse the JSON response - Handle potential errors robustly
        json_string = response.text.strip().lstrip('```json').rstrip('```').strip()
        if not json_string:
             print("Error: Gemini returned an empty response.")
             return None

        extracted_data = json.loads(json_string) #
        print("Successfully parsed JSON response from Gemini.")
        return extracted_data

    except json.JSONDecodeError as e:
        print(f"Error: Failed to decode JSON response from Gemini: {e}")
        print(f"Gemini Raw Response causing error:\n---\n{response.text}\n---") # Log the problematic response
        return None
    except Exception as e:
        # Catch other potential API errors (rate limits, auth issues, etc.)
        print(f"Error interacting with Gemini API: {e}")
        # You might want to inspect the 'response' object for more details if available
        # print(f"Full Gemini Response Object: {response}")
        return None

# --- Main Execution ---

def main():
    print("--- Job Application Markdown Creator (Selenium + Gemini) ---")
    job_url = input("1. Paste the Job Application URL: ")

    # 1. Fetch HTML using Selenium
    html_content = get_page_html_selenium(job_url)

    extracted_data = None
    if html_content:
        # 2. Extract relevant text using BeautifulSoup
        text_content = extract_relevant_text(html_content)

        if text_content:
            # 3. Extract structured data using Gemini
            extracted_data = extract_job_data_with_gemini(text_content, job_url)
        else:
            print("Skipping Gemini step as no relevant text could be extracted.")
    else:
        print("Skipping further steps as page HTML could not be fetched.")


    # 4. Process and Save Markdown File
    if extracted_data:
        print("Gemini extraction successful. Preparing Markdown file...")

        # Prepare final data dictionary
        final_data = {
            'company': extracted_data.get('company', '').strip(),
            'role': extracted_data.get('role', '').strip(),
            'location': extracted_data.get('location', '').strip(),
            'comp': extracted_data.get('comp', '').strip(),
            'req': extracted_data.get('req', '').strip(),
            'description': extracted_data.get('description', '').strip(),
            'link': job_url,
            'date_applied': datetime.date.today().strftime('%Y-%m-%d'),
            'applied': True,
            'recruiter_screen': '',
            'interview': False,
            'rejection': False,
            'declined': False,
            # Note: 'tags' is handled directly in create_markdown_content
        }

        # Create filename (Handle potential missing company/role)
        company_name = final_data.get('company')
        role_name = final_data.get('role')
        if not company_name and not role_name:
             base_filename = f"Job Posting {final_data['date_applied']}.md"
             print("Warning: Could not determine Company or Role from Gemini. Using generic filename.")
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
            return # Stop if directory can't be created

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
        print("\nCould not extract job data automatically using Gemini.")
        # Optional: Add fallback to manual input here if desired
        # print("Please enter the details manually.")
        # ... (reuse code from previous manual script if needed)


if __name__ == "__main__":
    main()