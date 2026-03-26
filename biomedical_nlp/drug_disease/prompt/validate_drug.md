You are a biomedical expert. Determine if {DRUG} is a drug in this text.

Title:
{TITLE}
Abstract:
{ABSTRACT}

A substance is considered a drug if it:
- Is designed or used therapeutically to treat, prevent, or diagnose disease
- Has established pharmaceutical properties or therapeutic effects
- Is part of a recognized drug class or family
- Demonstrates specific pharmacological activity for the condition

A substance is NOT a drug if it:
- Is a naturally occurring biological component without therapeutic modification
- Is an environmental compound or pollutant
- Functions only as a biomarker or diagnostic indicator
- Lacks clear therapeutic intent or pharmaceutical formulation

Consider the context carefully, especially for abbreviations or ambiguous terms.


Output:
{{
  "drug_valid": true / false,
  "confidence": 1-10
}}
