import PyPDF2
import os
import logging
import json
from typing import Optional, Dict, Any, List

logger = logging.getLogger("ResumeAnalyzerLogic")
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

def extract_text_from_pdf(pdf_path: str) -> Optional[str]:
    if not os.path.exists(pdf_path):
        logger.error(f"Resume PDF not found at path: {pdf_path}")
        return None
    try:
        text = ""
        with open(pdf_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                text += page.extract_text() or ""
        logger.info(f"Successfully extracted text from PDF: {pdf_path}")
        return text
    except Exception as e:
        logger.error(f"Error extracting text from PDF {pdf_path}: {e}", exc_info=True)
        return None

def analyze_resume_with_llm(resume_text: str, job_description_text: str) -> Dict[str, Any]:
    if not os.getenv("GEMINI_API_KEY"):
        return {"error": "LLM API key not configured."}
    
    llm_model_for_resume = os.getenv("GOOGLE_LLM_MODEL", "gemini-1.0-pro")
    if not llm_model_for_resume:
        return {"error": "LLM model not specified."}

    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    except ImportError:
        return {"error": "Google GenAI module not found."}

    model = genai.GenerativeModel(llm_model_for_resume)
    prompt = f"""
    You are an expert career coach and resume analyzer.
    Your task is to compare the provided resume content against the given job description.

    Resume Content:
    ---
    {resume_text[:4000]}
    ---

    Job Description:
    ---
    {job_description_text[:4000]}
    ---

    Based on this comparison, please provide the following in a JSON format:
    1.  "match_assessment": A qualitative assessment (e.g., "Strong Match", "Good Match").
    2.  "estimated_match_percentage": Your estimated percentage match (e.g., "around 70-80%").
    3.  "key_strengths": A list of 3-5 key strengths from the resume aligned with the JD.
    4.  "areas_for_improvement": A list of 3-5 specific, actionable suggestions for tailoring the resume.
    5.  "overall_summary": A brief (2-3 sentences) overall summary.

    Output ONLY the valid JSON object.
    """
    logger.info(f"🧠 Sending resume and JD to LLM ({llm_model_for_resume}) for analysis...")
    try:
        generation_config = genai.types.GenerationConfig(temperature=0.3)
        response = model.generate_content(prompt, generation_config=generation_config)
        analysis_text = response.text
        logger.info("🧠✅ LLM analysis received.")
        
        if analysis_text.strip().startswith("```json"):
            analysis_text = analysis_text.strip()[7:]
        if analysis_text.strip().endswith("```"):
            analysis_text = analysis_text.strip()[:-3]
        
        parsed_json = json.loads(analysis_text.strip())
        return parsed_json
    except json.JSONDecodeError as e:
        logger.error(f"🧠❌ LLM output for resume not valid JSON: {e}. Raw: {analysis_text[:300]}...")
        return {"error": "LLM output was not valid JSON.", "raw_llm_text": analysis_text}
    except Exception as e:
        logger.error(f"🧠❌ Error calling LLM for resume analysis: {e}", exc_info=True)
        return {"error": f"LLM API call failed: {str(e)}"}