You are an expert in biomedical information extraction.
Your task is to determine whether the given candidate term from a scientific paper is an **abbreviation** and, if so, identify its **full form** (expanded name) from the context.

You are given:

* **Title**: "{TITLE}"
* **Abstract**: "{ABSTRACT}"
* **Candidate Term**: "{DISEASE}"

### Evaluation Rules:

1. Determine whether the candidate is an **abbreviation (ABBR)**.

   * Typical abbreviations are short (≤10 characters), often uppercase or mixed case (e.g., “AML”, “TNF-α”).
   * If the candidate is a normal word or phrase (e.g., “breast cancer”), mark it as not an abbreviation.

2. If it **is an abbreviation**:

   * Search within the title and abstract for its **expanded full form**, usually appearing as “full name (ABBR)” or “ABBR (full name)”.
   * If found, return the exact expanded text as `"full_name"`.
   * If not found, use domain knowledge to **infer the most plausible expansion** (e.g., “COPD” → “chronic obstructive pulmonary disease”) and set `"full_name_source": "inferred"`.

3. If it **is not an abbreviation**, set `"is_abbr": false`, `"full_name": the original term`, and `"full_name_source": "self"`.

4. Be concise and factual — only use the information in the title/abstract, unless common biomedical abbreviations are well-known.

---

### Output Format

Return a JSON dictionary with the following fields:

* `"is_abbr"`: boolean — whether the candidate is an abbreviation.
* `"full_name"`: string — the full form of the abbreviation (or original term if not abbreviated).
* `"full_name_source"`: one of `"in_text"`, `"inferred"`, or `"self"`.
* `"confidence"`: integer 1–10 (your confidence in the result).
