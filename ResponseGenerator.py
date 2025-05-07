"""
Response Generation Module
Creates professional email responses for order confirmations, inquiries, and stock issues
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI
import textwrap
import time

@dataclass
class ProductInfo:
    id: str
    name: str
    description: str
    alternatives: List[str] = None

class ResponseGenerator:
    def __init__(self, llm, company_info: Dict):
        """
        Args:
            llm: Configured language model instance
            company_info: Dictionary containing:
                - name: Company name
                - contact_email: Support email
                - phone: Contact number
                - policy_url: Return policy link
        """
        self.llm = llm
        self.company = company_info
        self.templates = self._initialize_templates()

    def _initialize_templates(self) -> Dict:
        """Base templates for common scenarios"""
        return {
            "order_confirm": textwrap.dedent("""
                Thank you for your order! We're processing the following items:

                {order_details}

                Expected delivery: {delivery_date}
                Total amount: {total_amount}

                {company_info}
            """),
            "out_of_stock": textwrap.dedent("""
                We're sorry, some items aren't available:

                {unavailable_items}

                Alternatives we recommend:
                {alternatives}

                {company_info}
            """),
            "inquiry_response": textwrap.dedent("""
                Thank you for your question about {product_name}!

                Here's what we can share:
                {answer}

                For more details: {product_url}
                {company_info}
            """)
        }

    def _build_llm_chain(self, template: str) -> ChatPromptTemplate:
        """Create a configured LLM chain for dynamic responses"""
        return (
            {"context": RunnablePassthrough()}
            | ChatPromptTemplate.from_template(template)
            | self.llm
            | StrOutputParser()
        )

    def generate_order_confirmation(self, order_data: Dict) -> str:
        """
        Generate order confirmation email
        
        Args:
            order_data: {
                "order_id": str,
                "items": List[{"product_id", "name", "qty", "price"}],
                "delivery_date": str,
                "total": float
            }
        """
        order_details = "\n".join(
            f"- {item['qty']} x {item['name']} (${item['price']:.2f})"
            for item in order_data["items"]
        )

        template_vars = {
            "order_details": order_details,
            "delivery_date": order_data["delivery_date"],
            "total_amount": f"${order_data['total']:.2f}",
            "company_info": self._get_company_footer()
        }

        chain = self._build_llm_chain(self.templates["order_confirm"])
        return chain.invoke(template_vars)

    def generate_stock_response(self, 
                             unavailable_items: List[Dict],
                             alternatives: List[ProductInfo]) -> str:
        """
        Generate out-of-stock notification
        
        Args:
            unavailable_items: [
                {"product_id": str, "name": str, "requested_qty": int}
            ]
            alternatives: List of ProductInfo for suggestions
        """
        item_list = "\n".join(
            f"- {item['name']} (Requested: {item['requested_qty']})"
            for item in unavailable_items
        )

        alt_list = "\n".join(
            f"- {product.name}: {product.description[:100]}..."
            for product in alternatives
        ) if alternatives else "None available at this time"

        return self.templates["out_of_stock"].format(
            unavailable_items=item_list,
            alternatives=alt_list,
            company_info=self._get_company_footer()
        )

    def generate_product_response(self, 
                               question: str, 
                               product: ProductInfo,
                               knowledge_base: Optional[str] = None) -> str:
        """
        Generate detailed product inquiry response
        
        Args:
            question: Customer's original question
            product: ProductInfo dataclass
            knowledge_base: Additional context (manual/DB)
        """
        prompt = ChatPromptTemplate.from_template("""
            You're a customer service agent for {company}.
            Answer this question about {product}:
            Question: {question}
            Product details: {details}
            Additional context: {context}
            
            Respond in 2-3 paragraphs with:
            1. Direct answer to question
            2. Key product benefits
            3. Call-to-action
            
            Tone: Professional but friendly
        """)

        chain = prompt | self.llm | StrOutputParser()
        
        return chain.invoke({
            "company": self.company["name"],
            "product": product.name,
            "question": question,
            "details": product.description,
            "context": knowledge_base or "No additional context"
        })

    def _get_company_footer(self) -> str:
        """Standard company footer for all emails"""
        return (
            f"\n\n{self.company['name']} Customer Service\n"
            f"Email: {self.company['contact_email']} | "
            f"Phone: {self.company['phone']}\n"
            f"View our policies: {self.company['policy_url']}"
        )

    def generate_custom_response(self, 
                               scenario: str,
                               context: Dict) -> str:
        """
        Flexible generator for other scenarios
        
        Args:
            scenario: Response scenario key
            context: Variables for template formatting
            
        Supported scenarios:
            - 'return_request'
            - 'shipping_delay'
            - 'payment_issue'
        """
        custom_templates = {
            "return_request": """
                We've received your return request for:
                {items}
                
                Next steps:
                1. Package items securely
                2. Attach return label
                3. Ship within {days} days
                
                {company_info}
            """,
            "shipping_delay": """
                Important update about order {order_id}:
                
                Due to {reason}, your delivery is delayed by {delay}.
                
                New estimated arrival: {new_date}
                
                {company_info}
            """
        }

        if scenario not in custom_templates:
            raise ValueError(f"Unknown scenario: {scenario}")

        context["company_info"] = self._get_company_footer()
        return custom_templates[scenario].format(**context)