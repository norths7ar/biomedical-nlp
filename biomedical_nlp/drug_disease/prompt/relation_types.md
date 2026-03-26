You are a biomedical expert. Classify the Drug-Disease Relation between {chemical_name} and {disease_name} in this text.

Title:
{title}
Abstract:
{abstract}

You must evaluate **purely** based on the provided text, without external knowledge.

1. Choose ONE:

**side_effect**: Disease listed as TEAE/adverse event or most common TEAE, or {chemical_name} increases {disease_name} risk

**effective_treatment**: {chemical_name} treats/manages  {disease_name} or is studied for treatment

**ineffective_treatment**: Treatment explicitly failed with negative outcome clearly stated



3. **Co‑treatment rule**

   **If a treatment includes two or more drugs/ingredients and at least one of those components is known to cause an adverse event, assign the same adverse event to *every* component in that treatment.**
   *Rationale – treat the adverse event as a side effect of the entire co‑treatment, so all components inherit it.*

4. **Interaction rule**

   **If two drugs produce an adverse event only when taken together (i.e., neither drug causes it when used alone), assign that adverse event to *both* drugs.**
   *Rationale – the event stems from their interaction, so each drug is considered linked to the side effect when combined.*
   


5. If the relation between {chemical_name} and {disease_name} is not clearly stated in provided text, then  relation_type = no relation.

Key patterns:
- Treatment failure must be explicitly stated, not implied
- Default to effective_treatment for therapeutic studies

Base your decision ONLY on the provided text content.

Output:
{{
  "relation_type": "side_effect" | "effective_treatment" | "ineffective_treatment" | "no_relation",
  "confidence": 1-10
}}
