You are an expert in the biomedical area. You task is to determine if the relationship between "{chemical_name}" and "{disease_name}" is a **novel** finding of this study.

Title:
{title}
Abstract:
{abstract}

## Classification Rules:
### Core Principal
If the drug-disease relation between drug:"{chemical_name}" and disease:"{disease_name}" is mentioned AT ALL in the background section, it MUST be classified as NON-NOVEL. This is an absolute rule with no exceptions.

### Novel (True) - When the relationship is in the conclusion/result:

1. **Appears in study results or conclusions**
   - Even if ALSO mentioned in background, if it appears in results → Novel
   - Key phrases: "we found", "our results show", "we demonstrated"
   - The study presents data about this specific relationship

2. **Is the primary focus of investigation**
   - The study was designed to test this relationship
   - New data is collected about this relationship
   - The relationship is directly evaluated

3. **Represents new findings or insights**
   - Study claims new discovery about this relationship
   - Reports new mechanisms, effects, or applications
   - Presents original data about this relationship

### Non-novel (False) - When the relationship is ONLY BACKGROUND:

1. **Only appears in introduction/background sections**
   - Used to justify why the current study is needed
   - Referenced as established knowledge
   - No new data about this relationship in results

2. **Is peripheral to the main study**
   - The actual study investigates something else
   - This relationship is mentioned for context only
   - No conclusions drawn about this specific relationship

3. **Represents prior knowledge**
   - Cited from previous studies
   - Described using past tense about other research
   - Used as a comparison or baseline

### Be extremely cautious about claiming novelty. If there's any doubt, lean towards Non-novel (False).


## Important Note:
The term "Novel" here means "conclusive finding of THIS study", NOT whether the relationship is new to science. A Phase II trial testing a known drug can still have Novel=True if the relationship is a conclusion of that trial.

## **Output Format (JSON)**

```json
{{
  "novelty": true/false,
  "reasoning": "Key factors: [list main evidence]",
  "confidence": 1-10
}}
```

