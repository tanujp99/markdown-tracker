# Job Posting to Markdown Converter

This project contains Python scripts designed to scrape job posting information from a given URL, extract relevant details and the description using a Large Language Model (LLM), format the description, and save the result as a structured Markdown file.

Two versions are provided:
* `remote.py`: Uses the Google Generative AI (Gemini) API for LLM tasks.
* `local.py`: Uses a local LLM accessed via an OpenAI-compatible API endpoint (like LM Studio).

## Features

* Fetches full HTML content of a job posting URL using Selenium.
* Extracts the main job description text from the HTML using BeautifulSoup.
* Uses an LLM (either Remote or a Local model) to:
    * Extract structured data (Company, Role, Location, Compensation, Requisition ID) from the text.
    * Extract the plain text job description.
    * Format the extracted plain text description using Markdown.
* Creates a Markdown file (`.md`) with YAML frontmatter containing the extracted structured data and the formatted description.
* Automatically names the Markdown file based on the company and role (e.g., `Company Name - Role Name.md`).
* Handles potential errors during web scraping and LLM interaction.
* Configurable via a `.env` file.

## Files

* `remote.py`: The main script using the Google Generative AI (Gemini) API.
* `local.py`: The main script using a local OpenAI-compatible LLM API.
* `requirements.txt`: Lists the necessary Python packages.
* `.env` (You need to create this): File to store configuration variables like API keys and paths.

## Setup

1.  **Clone or Download:** Get the script files (`remote.py`, `local.py`, `requirements.txt`).
2.  **Install Dependencies:** Make sure you have Python 3 installed. Open your terminal or command prompt in the project directory and run:
    ```bash
    pip install -r requirements.txt
    ```
    This will install all the necessary libraries listed in `requirements.txt`[cite: 1].

3.  **Install WebDriver:** The script uses `webdriver-manager` which should automatically download and manage ChromeDriver. If you encounter issues, ensure you have Google Chrome installed.
4.  **Create `.env` File:** Create a file named `.env` in the same directory as the scripts. Add the following configuration variables:

    * **For `remote.py`:**
        ```dotenv
        # Your Google Generative AI API Key (Required for remote.py)
        REMOTE_LLM_API_KEY=YOUR_GEMINI_API_KEY

        # Path where the Markdown files will be saved (Required for both scripts)
        MARKDOWN_SAVE_PATH=/path/to/your/markdown/notes/folder
        ```

    * **For `local.py`:**
        ```dotenv
        # Base URL of your local OpenAI-compatible API server (e.g., LM Studio) (Required for local.py)
        LOCAL_LLM_BASE_URL=http://localhost:1234/v1

        # Path where the Markdown files will be saved (Required for both scripts)
        MARKDOWN_SAVE_PATH=/path/to/your/markdown/notes/folder
        ```
        *(Note: `local.py` assumes the local LLM API doesn't require an API key (`LOCAL_LLM_API_KEY="not-needed"` is used internally))*

5.  **Replace Placeholders:**
    * In the `.env` file, replace `REMOTE_LLM_API_KEY` with your actual Google Generative AI API key if using `remote.py`.
    * Replace `/path/to/your/markdown/notes/folder` with the actual absolute or relative path where you want the generated Markdown files to be saved.
    * If using `local.py`, ensure `LOCAL_LLM_BASE_URL` points to your running local LLM server endpoint.

6.  **(If using `local.py`) Start Local LLM Server:** Ensure your local LLM (e.g., via LM Studio) is running and serving a model via the OpenAI-compatible API endpoint specified in `LOCAL_LLM_BASE_URL`.

## Usage

1.  Open your terminal or command prompt.
2.  Navigate to the directory containing the scripts and your `.env` file.
3.  Run the desired script using Python:

    * **To use the Remote API:**
        ```bash
        python remote.py
        ```

    * **To use the Local LLM:**
        ```bash
        python local.py
        ```

4.  The script will prompt you to paste the job application URL:
    ```
    - Paste the Job Application URL:
    ```
5.  Paste the URL and press Enter.
6.  The script will then:
    * Launch a browser window (headless by default) using Selenium to load the page.
    * Extract text content.
    * Communicate with the configured LLM (Remote or Local) to extract data and format the description.
    * Save the results as a `.md` file in the `MARKDOWN_SAVE_PATH` specified in your `.env` file.
    * Print the path to the created file upon success or display error messages if issues occur.

## Choosing Between Scripts

* **`remote.py`:**
    * **Pros:** Uses a powerful cloud-based model which may yield better extraction and formatting results. No need to run a local model.
    * **Cons:** Requires a Generative AI API key and incurs potential API usage costs. Relies on internet connectivity to the API.
* **`local.py`:**
    * **Pros:** Runs entirely locally (after initial setup). No external API costs. Potentially faster response times depending on your hardware. Works offline (if the job page is accessible).
    * **Cons:** Requires setting up and running a local LLM server (like LM Studio). The quality of results depends heavily on the specific local model being used. May require significant RAM/VRAM.

Choose the script that best suits your needs regarding privacy, cost, performance, and technical setup preference.