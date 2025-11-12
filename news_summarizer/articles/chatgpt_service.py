from django.conf import settings
from django.core.cache import caches
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

SUMMARY_CACHE = caches['summaries']

# Replacing the Mock with the actual function
def summarize_article_with_chatgpt(title: str, content: str) -> str:
    """
    Connects to the OpenAI API to generate a summary for an article.
    """
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == 'YOUR_DEFAULT_OPENAI_KEY':
        logger.warning("OPENAI_API_KEY is not configured, falling back to a mock summary.")
        # If the key is missing, we use a mock summary as a Fallback
        return f"**Mock Summary (Fallback):** The article discusses the topic {title}. An OpenAI API key must be configured."
        
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        # Instructions for the model (System Prompt)
        system_prompt = "You are an expert news summarizer. Your task is to provide a concise, objective summary of the provided article content. Keep the summary under 100 words."
        
        # The full content sent to the model (User Content)
        user_content = f"Title: {title}\n\nContent:\n{content}"
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", # Can be changed to "gpt-4o"
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.3
        )
        
        # Retrieving the content from the response
        summary = response.choices[0].message.content
        return summary
        
    except openai.APIError as e:
        logger.error(f"OpenAI API Error: {e}")
        return f"OpenAI API Error: Could not summarize the article ({e})."
    except Exception as e:
        logger.error(f"Unexpected error during summarization: {e}")
        return f"General summarization error: ({e})."


def get_article_summary_with_caching(title: str, content: str):
    """
    Returns an article summary. Checks the Cache first.
    """
    cache_key = f"summary:{title[:50]}" 
    
    # 1. Check cache
    summary_text = SUMMARY_CACHE.get(cache_key)
    if summary_text is not None:
        logger.info(f"Summary returned from cache for: {title}")
        return summary_text, True # True = retrieved from cache
    
    # 2. Generate a new summary (using the actual function)
    logger.info(f"Generating new summary (calling ChatGPT) for: {title}")
    
    new_summary = summarize_article_with_chatgpt(title, content)
    
    # 3. Save the summary to the cache
    SUMMARY_CACHE.set(cache_key, new_summary, timeout=86400) # 24 hours
    
    return new_summary, False # False = newly generated