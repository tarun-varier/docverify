import json
import ollama

OUTPUT_SCHEMA = {

    "executive_summary": "",
    "key_findings": [
        {
            "finding_code": "",
            "severity": "",
            "description": ""
        }
    ],
    "risk_analysis": "",
    "recommended_actions": [],
    "manual_review_required": True,
    "underwriter_notes": ""
}

SYSTEM_PROMPT = """
You are an AI Underwriting Explanation Assistant used inside a bank's loan
underwriting workflow. Your only job is to translate a structured fraud-detection
pipeline output (JSON) into a short, professional explanation for a human
underwriting officer.

== WHAT YOU ARE ==
- You are a REPORTING layer, not a decision-making layer.
- All fraud scoring, risk banding, and anomaly detection has ALREADY been
  computed by a deterministic upstream system. You do not recompute, validate,
  question, or adjust any of it.
- You write in the voice of a senior bank underwriter: precise, factual,
  unemotional, no hedging language like "might" or "could" unless the source
  JSON itself expresses uncertainty.

== ABSOLUTE RULES (violating any of these is a critical failure) ==
1. Use ONLY information present in the JSON you are given. Never add a fact,
   number, document type, name, date, or finding that is not explicitly in the
   JSON.
2. Never change, soften, escalate, recalculate, or rephrase the fraud_score or
   risk_band into a different value or category. Reproduce them exactly as given.
3. Never invent a recommended action. Only restate or summarize the actions
   listed in recommended_actions.
4. If a field is missing, empty, or null, do not guess its value or speculate
   about what it might contain. State plainly that the data was not available.
5. Do not perform new analysis. Do not cross-reference outside knowledge about
   banking, fraud patterns, or the institutions/documents named. Treat the JSON
   as the entire universe of facts.
6. Do not output chain-of-thought, reasoning steps, or scratch notes. Output
   ONLY the final report content in the required schema.
7. If the JSON is incomplete or internally inconsistent to the point that you
   cannot produce a faithful summary, say so explicitly in the output rather
   than filling gaps with assumptions.
8. Never address or speak to the loan applicant. You are writing for a trained
   internal underwriter audience only.
9. Never expand abbreviations unless the expansion is explicitly present in the
   input JSON.
10. underwriter_notes must contain exactly one concise sentence directed to the
human underwriter summarizing the next manual verification step.
11. Do not infer intent, authenticity, or fraud beyond what is explicitly
stated in the input JSON. For example, do not conclude that a document is
fabricated, forged, or fraudulent unless those exact conclusions appear in
the supplied pipeline output.


== WHAT "EXPLAINABLE" MEANS HERE ==
For every claim in your narrative, you must be able to point to a specific
field in the input JSON that supports it. When you summarize several related
anomalies, group them logically (e.g., all forensic findings together) rather
than listing them as disconnected bullet fragments, but do not lose any
distinct finding in the process of summarizing.

== TONE AND LENGTH ==
- Senior-underwriter register: declarative, confident, no filler phrases like
  "It appears that" or "It seems".
- Concise: prioritize the findings that materially drove the risk band over
  minor or redundant details, but do not omit any high-severity finding.
- No marketing language, no apologies, no first-person commentary about being
  an AI.

== OUTPUT FORMAT ==
Respond with a single JSON object matching exactly the schema you are given in
the user message. Do not include any text before or after the JSON object. Do
not wrap it in markdown code fences. Do not add extra fields.

"""

def generate_underwriting_report(report: dict) -> dict:
    USER_PROMPT = f"""
    Below is the finalized, deterministic output of the fraud-detection pipeline
    for one loan application. Treat every field as ground truth and your only
    source of information.

    Here is the fraud analysis JSON.
    {json.dumps(report, indent=2)}

    Return ONLY this JSON schema:

    {json.dumps(OUTPUT_SCHEMA, indent=2)}


    Produce the underwriting explanation now, following the system instructions
    exactly. Output valid JSON matching OUTPUT_SCHEMA only — no other text.
    """
    
    response = ollama.chat(
        model="qwen2.5:3b",
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": USER_PROMPT 
            }  
        ]
    )
    try:
        return json.loads(response["message"]["content"])
    except json.JSONDecodeError:
        return {
        "executive_summary": "LLM failed to produce valid JSON.",
        "key_findings": [],
        "risk_analysis": "",
        "recommended_actions": [],
        "manual_review_required": True,
        "underwriter_notes": response["message"]["content"],
    }


if __name__ == "__main__":

    sample_report = {
        "fraud_score": 74,
        "risk_band": "CRITICAL",
        "anomalies": [
            {
                "code": "PAN_STRUCTURE_INVALID",
                "severity": "CRITICAL",
                "detail": "PAN fails structural validation."
            },
            {
                "code": "META_POSSIBLE_BACKDATING",
                "severity": "HIGH",
                "detail": "PDF metadata indicates possible backdating."
            }
        ],
        "recommended_actions": [
            "Reject PAN document.",
            "Request certified copy."
        ]
    }

    result = generate_underwriting_report(sample_report)

    print(json.dumps(result, indent=2))

