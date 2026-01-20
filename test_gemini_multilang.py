"""
Test Gemini Multilingual Support (FR/EN/HE)
MISSION A: Prouver que Gemini répond correctement dans les 3 langues
"""

import os
import logging
from pathlib import Path
import google.genai as genai

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Gemini configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')

def test_gemini_language(lang: str, lang_full: str):
    """
    Test Gemini API with specific language enforcement
    
    Args:
        lang: Language code (fr/en/he)
        lang_full: Full language name (French/English/Hebrew)
    """
    
    logging.info(f"\n{'='*80}")
    logging.info(f"TEST GEMINI LANGUAGE: {lang.upper()} ({lang_full})")
    logging.info(f"{'='*80}")
    
    if not GEMINI_API_KEY:
        logging.error("❌ GEMINI_API_KEY not configured")
        return {
            "lang": lang,
            "success": False,
            "error": "GEMINI_API_KEY missing"
        }
    
    try:
        # Initialize Gemini client
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Language-enforced prompt
        prompts = {
            "fr": """Vous êtes un expert en conseil stratégique pour le marché israélien.

RÈGLE ABSOLUE: Vous DEVEZ répondre UNIQUEMENT en français. Si vous utilisez une autre langue, retournez: LANG_FAIL.

Analysez brièvement (3-4 lignes) les opportunités pour une marque de restauration française souhaitant s'implanter en Israël.

Répondez UNIQUEMENT en français.""",
            
            "en": """You are a strategic consultant for the Israeli market.

ABSOLUTE RULE: You MUST answer ONLY in English. If you output any other language, return: LANG_FAIL.

Briefly analyze (3-4 lines) the opportunities for a French restaurant brand wanting to expand to Israel.

Answer ONLY in English.""",
            
            "he": """אתה יועץ אסטרטגי לשוק הישראלי.

כלל מוחלט: אתה חייב לענות רק בעברית. אם אתה משתמש בשפה אחרת, החזר: LANG_FAIL.

נתח בקצרה (3-4 שורות) את ההזדמנויות למותג מסעדה צרפתי המעוניין להתרחב לישראל.

ענה רק בעברית."""
        }
        
        prompt = prompts.get(lang, prompts["en"])
        
        # Log request details
        logging.info(f"MODEL: {GEMINI_MODEL}")
        logging.info(f"LANG_REQUESTED: {lang}")
        logging.info(f"PROMPT_LENGTH: {len(prompt)} chars")
        
        # Call Gemini API
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[prompt]
        )
        
        # Extract response text
        response_text = response.text if hasattr(response, 'text') else str(response)
        
        # Check for LANG_FAIL
        lang_fail_detected = "LANG_FAIL" in response_text
        
        # Get token usage if available
        tokens = "N/A"
        if hasattr(response, 'usage_metadata'):
            tokens = f"in:{response.usage_metadata.prompt_token_count} out:{response.usage_metadata.candidates_token_count}"
        
        # Log results
        logging.info(f"STATUS: {'❌ LANG_FAIL DETECTED' if lang_fail_detected else '✅ SUCCESS'}")
        logging.info(f"TOKENS: {tokens}")
        logging.info(f"RESPONSE_LENGTH: {len(response_text)} chars")
        logging.info(f"FIRST_200_CHARS: {response_text[:200]}")
        
        if lang_fail_detected:
            logging.error(f"❌ Gemini failed to respond in {lang_full} - LANG_FAIL detected")
        
        # Detailed output for verification
        logging.info(f"\n--- FULL RESPONSE ({lang.upper()}) ---")
        logging.info(response_text)
        logging.info(f"--- END RESPONSE ({lang.upper()}) ---\n")
        
        return {
            "lang": lang,
            "lang_full": lang_full,
            "success": not lang_fail_detected,
            "response_length": len(response_text),
            "first_200": response_text[:200],
            "full_response": response_text,
            "tokens": tokens,
            "model": GEMINI_MODEL
        }
        
    except Exception as e:
        logging.error(f"❌ Error testing language {lang}: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        
        return {
            "lang": lang,
            "success": False,
            "error": str(e)
        }


def main():
    """Run all language tests"""
    
    logging.info(f"\n{'#'*80}")
    logging.info(f"# GEMINI MULTILINGUAL TEST SUITE")
    logging.info(f"# Model: {GEMINI_MODEL}")
    logging.info(f"# API Key: {'Configured' if GEMINI_API_KEY else 'NOT CONFIGURED'}")
    logging.info(f"{'#'*80}\n")
    
    if not GEMINI_API_KEY:
        logging.error("❌ GEMINI_API_KEY environment variable not set")
        logging.error("Please configure GEMINI_API_KEY before running tests")
        return
    
    # Run tests for each language
    results = []
    
    # Test 1: French
    results.append(test_gemini_language("fr", "French"))
    
    # Test 2: English
    results.append(test_gemini_language("en", "English"))
    
    # Test 3: Hebrew
    results.append(test_gemini_language("he", "Hebrew"))
    
    # Summary
    logging.info(f"\n{'='*80}")
    logging.info("TEST SUMMARY")
    logging.info(f"{'='*80}")
    
    for result in results:
        status = "✅ PASS" if result.get("success") else "❌ FAIL"
        lang_display = f"{result['lang'].upper()} ({result.get('lang_full', 'Unknown')})"
        logging.info(f"{status} - {lang_display}")
        
        if not result.get("success"):
            error = result.get("error", "Language enforcement failed")
            logging.info(f"  Error: {error}")
    
    # Overall result
    all_passed = all(r.get("success") for r in results)
    logging.info(f"\n{'='*80}")
    if all_passed:
        logging.info("✅ ALL TESTS PASSED - Gemini supports FR/EN/HE correctly")
    else:
        logging.error("❌ SOME TESTS FAILED - Review implementation")
    logging.info(f"{'='*80}\n")
    
    return results


if __name__ == "__main__":
    main()
