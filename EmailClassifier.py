"""
Email Classification Module
Uses LLMs to categorize emails as 'product inquiry' or 'order request'
"""

from typing import Dict, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm
import time

class EmailClassifier:
    """LLM-powered email classification system with retry mechanisms and validation."""

    def __init__(self, llm_config: Dict):
        """
        Initialize classifier with LLM configuration.
        
        Args:
            llm_config: Dictionary containing:
                - api_key: OpenAI API key
                - base_url: API endpoint URL
                - model_name: LLM model identifier
                - temperature: LLM creativity setting (0-1)
        """
        self.llm = self._initialize_llm(llm_config)
        self.classification_chain = self._build_classification_chain()
        self.classification_cache = {}  # For duplicate email handling

    def _initialize_llm(self, config: Dict) -> ChatOpenAI:
        """Configure the LLM with proper error handling."""
        try:
            return ChatOpenAI(
                model=config.get("model_name", "gpt-4"),
                temperature=config.get("temperature", 0),
                openai_api_key=config["api_key"],
                openai_api_base=config["base_url"],
                max_retries=3
            )
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
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
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
                result = "order request"
            elif "product" in result or "inquiry" in result:
                result = "product inquiry"
            else:
                result = "product inquiry"  # Default fallback
                
            self.classification_cache[email_hash] = result
            return result
            
        except Exception as e:
            print(f"Classification failed for email {email.get('id', 'unknown')}: {e}")
            raise

    def classify_batch(self, emails: List[Dict], batch_size: int = 20) -> List[Dict]:
        """
        Process multiple emails with rate limiting and progress tracking.
        
        Args:
            emails: List of dictionaries with:
                - id: Unique email identifier
                - subject: Email subject line
                - message: Email body content
            batch_size: Number of emails to process between pauses
            
        Returns:
            List of classification results with original IDs
        """
        if not emails:
            return []
            
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
                        "category": "unclassified",
                        "error": str(e)
                    })
            
            time.sleep(1.5)  # Rate limiting
            
        return results

    def get_classification_rules(self) -> str:
        """Return the current classification criteria for auditing."""
        return self.classification_chain.prompt.template