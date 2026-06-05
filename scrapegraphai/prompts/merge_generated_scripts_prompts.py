"""
merge_generated_scripts_prompts module
"""

TEMPLATE_MERGE_SCRIPTS_PROMPT = """
You are a python expert in web scraping and you have just generated multiple scripts to scrape different URLs.\n
The scripts are generated based on a user question and the content of the websites.\n
You need to create one single script that merges the scripts generated for each URL.\n
The scraped contents are in a JSON format and you need to merge them based on the context and providing a correct JSON structure.\n
The output should be just in python code without any comment and should implement the main function.\n
The python script, when executed, should format the extracted information sticking to the user question and scripts output format.\n

CRITICAL — THE TARGET URL(s) ARE EXACTLY:\n
{source_urls}\n
You MUST keep these exact URLs in every page.goto() and requests.get() call.\n
DO NOT change, guess, or infer any other URL. Using a different URL is a hard bug.\n
Also, NEVER use wait_until="networkidle" — it hangs on modern sites.\n

USER PROMPT: {user_prompt}\n
SCRIPTS:\n
{scripts}
"""
