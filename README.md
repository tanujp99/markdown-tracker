# Obsidian Job Hunting System

This project provides a framework for tracking job applications using Python scripts to automate data entry into an Obsidian vault. It combines web scraping and LLM processing to create structured notes for each application, which can then be visualized and managed within Obsidian using Dataview.

## Overview

The system consists of two main parts:

1.  **Python Scripts (`scripts/`):** These scripts fetch job posting details from a URL, extract key information using an LLM (either remote or local), and automatically create a new Markdown note in your Obsidian vault based on a template.
2.  **Obsidian Templates (`templates/`):** These provide the structure for your job hunting vault.
    * A template for individual job application notes (`Company - Position.md`) with YAML frontmatter for tracking details.
    * A dashboard (`Stats.md`) using the Dataview plugin to visualize application statistics and progress.

The goal is to streamline the process of saving job application details and provide a dynamic way to track your job hunt within Obsidian.

## Components

### 1. `scripts/` Folder

This folder contains the core automation logic.

* `remote.py` / `local.py`: Python scripts that take a job posting URL as input. They use Selenium to scrape the page, an LLM (Google Gemini via API or a local model via an OpenAI-compatible endpoint) to parse the content, and then generate a Markdown file (`.md`) for the job application.
* `requirements.txt`: Lists the Python dependencies needed to run the scripts.
* `README.md`: Detailed instructions on setting up and running the Python scripts (API keys, environment variables, choosing between remote/local LLMs).

*(Refer to the `scripts/README.md` for detailed setup and usage instructions for the Python scripts.)*

### 2. `templates/` Folder

This folder contains the Markdown files intended for use within your Obsidian vault.

* `Company - Position.md`: The template used by the Python scripts to create new job application notes. It includes YAML frontmatter for structured data like company, role, location, application date, status flags (applied, interview, rejection), compensation, requisition ID, and the original link. The main body is populated with the formatted job description extracted by the scripts.
* `Stats.md`: An Obsidian dashboard page. It uses DataviewJS queries to generate dynamic statistics based on the frontmatter in your job notes, including total application counts, daily/weekly application charts, and applications per company. It may also include embedded queries or links to other Obsidian notes/views for managing tasks or boards.
* `README.md`: Provides specific information about setting up the templates within Obsidian, including required community plugins (Dataview, Charts) and potentially path configurations.

*(Refer to the `templates/README.md` for details on Obsidian setup for these templates.)*

## Workflow

1.  **Setup Obsidian:**
    * Create an Obsidian vault (or use an existing one).
    * Copy the files from the `templates/` directory into your vault (e.g., into a `Job Hunt` folder).
    * Install the required Obsidian community plugins: `Dataview` and `Charts`.
    * Configure the `Stats.md` page if needed (e.g., update Dataview query paths like `"Hunt/Post"` if you place your job notes elsewhere).
2.  **Setup Python Scripts:**
    * Follow the instructions in `scripts/README.md` to install dependencies and configure the `.env` file (API keys, save path pointing to your Obsidian vault's job notes folder).
3.  **Run a Script:**
    * Execute `python remote.py` or `python local.py` from the `scripts` directory in your terminal.
    * Paste the URL of a job posting when prompted.
4.  **Review in Obsidian:**
    * The script will create a new `.md` file in the specified vault location (e.g., `Hunt/Post/Company Name - Role Name.md`).
    * Open Obsidian. The new note should appear, populated with data.
    * View the `Stats.md` page to see updated statistics and charts reflecting the new application.

## Customization

* **Save Path:** Ensure the `MARKDOWN_SAVE_PATH` in the scripts' `.env` file points to the correct folder within your Obsidian vault where you want job notes saved (e.g., `/path/to/vault/Hunt/Post`).
* **Dataview Queries:** Adjust the paths and filters in the DataviewJS blocks within `Stats.md` to match your vault structure and desired statistics.
* **Template:** Modify `templates/Company - Position.md` if you want to add or change the fields tracked in the YAML frontmatter. Remember to update the Python scripts (`create_markdown_content` function) if you make structural changes.
