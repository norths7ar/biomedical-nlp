You are an expert in biomedical information extraction. Your task is to validate whether the following term is correctly recognized as a **Disease or Pathological Condition** in the given scientific paper.

You are given:

- **Title**: "{TITLE}"
- **Abstract**: "{ABSTRACT}"
- **Disease Candidate**: "{DISEASE}"

### Evaluation Criteria:

Only return `true` if it refers to a **health-related condition** — a disease, disorder, diagnosis, or pathological state — and not merely a biological phenomenon.

### Output Format:

Return a JSON dictionary with:

- `"disease_valid"`: `true` if it is a valid disease/pathology; otherwise `false`.
- `"reasoning"`: a brief explanation.
- `"confidence"`: integer 1–10 (your confidence in the answer).

Only use information from the title and abstract. When uncertain, return `false`.
