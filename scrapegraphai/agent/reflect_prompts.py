"""
Reflection prompts — teach the LLM to diagnose and fix scraper failures.
"""

TEMPLATE_ERROR_ANALYSIS = """
You are an expert Python debugger for Playwright web scrapers.

The scraper script below FAILED with the following error:

  ERROR TYPE: {error_type}
  ERROR SUMMARY: {error_summary}

  STDERR:
  {stderr}

  STDOUT:
  {stdout}

The CURRENT script is:
```python
{script}
```

Your job: fix the script so it runs successfully and extracts the data.

RULES:
1. If the error is a NameError (undefined variable) → fix the variable name.
2. If the error is a Timeout (selector not found) → the CSS selector is wrong.
   Look for what selectors ARE available in the HTML and use those instead.
   Common correct selectors on gov sites: li.ndm-item, .ndm-result-title a.
3. If the error is 403 Forbidden → add stronger anti-detection measures:
   - headless=False (never True)
   - realistic viewport, user_agent, timezone, Accept-Language headers
   - proxy via os.environ.get("HTTPS_PROXY", "http://127.0.0.1:7890")
   - await page.add_init_script to strip navigator.webdriver
4. If the output is empty or the selector timed out → the CSS selectors
   don't match. Replace them with ones that DO exist on the page.
5. NEVER change the target URL unless it's clearly a typo in the code.
6. Use json.dumps() to escape any Python variable embedded in JavaScript.
7. For pagination, use fingerprint-based detection (compare first item's
   innerText), NOT count-based detection.
8. Output ONLY the complete corrected Python script — no explanation,
   no markdown fences, just the raw code.
"""
