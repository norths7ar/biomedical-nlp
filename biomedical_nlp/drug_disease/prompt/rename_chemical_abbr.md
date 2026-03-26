You are an expert in biomedical information extraction.
Your task is to determine whether the given candidate term from a scientific paper is an **abbreviation of a chemical or drug name**, and, if so, identify its **full form** (expanded name) from the context.

You are given:

* **Title**: "{TITLE}"
* **Abstract**: "{ABSTRACT}"
* **Candidate Term**: "{CHEMICAL}"

---

### Evaluation Rules:

1. Determine whether the candidate is an **abbreviation (ABBR)**.

   * Typical chemical or drug abbreviations are short (≤10 characters), often uppercase or mixed case, and may contain digits, hyphens, or chemical symbols (e.g., “5-FU”, “DOX”, “MTX”, “CDDP”).
   * If the candidate is already a full name (e.g., “doxorubicin”, “cisplatin”), mark it as not an abbreviation.

2. If it **is an abbreviation**:

   * Search within the title and abstract for its **expanded full form**, usually appearing as “full name (ABBR)” or “ABBR (full name)”.
   * If found, return the exact expanded text as `"full_name"` and set `"full_name_source": "in_text"`. 
   * If not found, use domain knowledge to **infer the most plausible expansion** (e.g., “DOX” → “doxorubicin”, “5-FU” → “5-fluorouracil”, “MTX” → “methotrexate”) and set `"full_name_source": "inferred"`.

3. If it **is not an abbreviation**, set:
   * `"is_abbr": false`
   * `"full_name"`: the original term
   * `"full_name_source": "self"`

4. Be concise and factual — only use information in the title/abstract, unless the abbreviation is a **well-known drug abbreviation** in biomedical literature.

---

### Output Format

Return a JSON dictionary with the following fields:

* `"is_abbr"`: boolean — whether the candidate is an abbreviation.
* `"full_name"`: string — the full form of the abbreviation (or original term if not abbreviated).
* `"full_name_source"`: one of `"in_text"`, `"inferred"`, or `"self"`.
* `"confidence"`: integer 1–10 (your confidence in the result).
