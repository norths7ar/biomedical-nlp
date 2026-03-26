You are an expert in bioscience. You will be given an abstract about a specific disease, along with a list of extracted drug–disease relations. Each relation represents a pair of (drug, disease) that was detected from the same abstract.

Some drugs may be discussed independently (single-drug therapy) and/or as part of a combination/cotreatment regimen. Your task is to determine the actual treatment structure used in the text.

Please follow these instructions:
1. Identify whether any of the given drugs are used together as a combination/cotreatment regimen.
2. If yes, specify which of the listed drugs form each combination and summarize the evidence briefly.
3. If no combination is mentioned or implied, confirm that all of the listed drugs are independent.
4. Assign a confidence score (1–10) to each decision.

Return your answer strictly in the following JSON format:
{
  "has_combination": true | false,
  "combination_groups": [
    {
      "drugs": ["DrugA", "DrugB"],
      "confidence": 8,
      "comment": "DrugA and DrugB were used together as a combination therapy."
    }
  ],
  "single_drug_relations": [
    {
      "drug": "DrugC",
      "confidence": 9,
      "comment": "DrugC was used alone."
    }
  ]
}

Important rules:
- Do NOT assume all drugs are combined unless the text explicitly or strongly implies combination therapy.
- Some drugs may appear both in combinations and independently; handle each case separately.
- Confidence must be an integer between 1 and 10.
- If no combination is found, set "has_combination" to false and leave "combination_groups" empty.
- **In "single_drug_relations", only include drugs from the input list that are explicitly described as independent.**
