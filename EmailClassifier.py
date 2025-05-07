
from typing import Dict, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class EmailClassifier:
    """LLM-powered email classification system with retry mechanisms and validation."""

    def __init__(self):
        """
        Initialize classifier using centralized configuration from .env and config files.
        No longer requires manual llm_config parameter.
        """
        self.llm = self._initialize_llm()
        self.classification_chain = self._build_classification_chain()
        self.classification_cache = {}  # For duplicate email handling
        self.rate_limit_delay = float(os.getenv("RATE_LIMIT_DELAY", "1.5"))

    def _initialize_llm(self) -> ChatOpenAI:
        """Configure the LLM using environment variables"""
        try:
            return ChatOpenAI(
                model=os.getenv("LLM_MODEL", "gpt-4"),
                temperature=float(os.getenv("LLM_TEMPERATURE", "0")),
                openai_api_key=os.getenv("OPENAI_API_KEY"),
                openai_api_base=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
                max_retries=int(os.getenv("LLM_MAX_RETRIES", "3"))
        except Exception as e:
            raise ValueError(f"LLM initialization failed: {str(e)}")

    def _build_classification_chain(self):
        """Construct the classification pipeline with examples."""
        classification_prompt = ChatPromptTemplate.from_template(
            """Analyze this email and classify its intent:
            
            **Order Request Indicators**:
            - Specific product references (SKU, model numbers)
            - Quantity specifications ("2 units", "all available")
            - Purchase verbs ("buy", "order", "ship")
            - Payment/shipping details
            
            **Product Inquiry Indicators**:
            - Question words ("how", "what", "does")
            - Feature requests ("color options", "dimensions")
            - Comparison requests ("vs X product")
            - General information
            
            **Examples**:
            Order: "Please send 3 units of LTH-0978 to my NJ warehouse"
            Inquiry: "What material is used in the winter collection jackets?"
            
            **Email to Classify**:
            Subject: {subject}
            Content: {message}
            
            Respond ONLY with either:
            - "order request"
            - "product inquiry"
            """
        )
        
        return (
            {
                "subject": RunnableLambda(self._clean_text),
                "message": RunnableLambda(self._clean_text)
            }
            | classification_prompt
            | self.llm
            | StrOutputParser()
        )

    def _clean_text(self, text: str) -> str:
        """Sanitize input text for LLM processing."""
        return text.strip()[:2000]  # Prevent token overflow

    @retry(
        stop=stop_after_attempt(int(os.getenv("CLASSIFICATION_RETRY_ATTEMPTS", "3"))),
        wait=wait_exponential(
            multiplier=1,
            min=float(os.getenv("RETRY_DELAY_MIN", "2")),
            max=float(os.getenv("RETRY_DELAY_MAX", "10"))
        ),
        reraise=True
    )
    def _classify_single(self, email: Dict) -> str:
        """Classify one email with validation and caching."""
        email_hash = hash(f"{email['subject']}{email['message']}")
        
        if email_hash in self.classification_cache:
            return self.classification_cache[email_hash]
        
        try:
            result = self.classification_chain.invoke(email).lower().strip()
            
            # Validation layer
            if "order" in result:
                result = os.getenv("CLASSIFICATION_ORDER", "order request")
            else:
                result = os.getenv("CLASSIFICATION_INQUIRY", "product inquiry")
                
            self.classification_cache[email_hash] = result
            return result
            
        except Exception as e:
            print(f"Classification failed for email {email.get('id', 'unknown')}: {e}")
            raise

    def classify_batch(self, emails: List[Dict], batch_size: int = None) -> List[Dict]:
        """
        Process multiple emails with rate limiting and progress tracking.
        
        Args:
            emails: List of dictionaries with:
                - id: Unique email identifier
                - subject: Email subject line
                - message: Email body content
            batch_size: Number of emails to process between pauses (default from env)
            
        Returns:
            List of classification results with original IDs
        """
        if not emails:
            return []
            
        batch_size = batch_size or int(os.getenv("BATCH_SIZE", "20"))
        results = []
        
        for i in tqdm(range(0, len(emails), batch_size), 
                    desc="Classifying emails",
                    unit="batch"):
            
            batch = emails[i:i+batch_size]
            for email in batch:
                try:
                    classification = self._classify_single(email)
                    results.append({
                        "email_id": email["id"],
                        "category": classification
                    })
                except Exception as e:
                    results.append({
                        "email_id": email["id"],
                        "category": os.getenv("CLASSIFICATION_UNKNOWN", "unclassified"),
                        "error": str(e)
                    })
            
            time.sleep(self.rate_limit_delay)
            
        return results

    def get_classification_rules(self) -> str:
        """Return the current classification criteria for auditing."""
        return self.classification_chain.prompt.template