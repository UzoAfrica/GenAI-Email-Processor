# **GenAI Email Processor**  

## **Project Overview**  
The **GenAI Email Processor** is an AI-powered system designed to automate email classification, order processing, and customer inquiries using **Large Language Models (LLMs)**. It processes emails from a given dataset, categorizes them, checks product availability, generates order confirmations, and responds to product-related questions—all while dynamically updating stock levels.  


### **Key Features**  
 **Email Classification** – Automatically categorizes emails as either **"product inquiry"** or **"order request"** using LLM-based intent detection.  

 **Order Processing & Stock Management** –  
- Verifies product availability in real time.  
- Updates stock levels based on order fulfillment.  
- Generates order statuses (`"created"` or `"out of stock"`).
  

 **Automated Response Generation** –  
- Sends **personalized, production-ready emails** for:  
  - Successful orders (with product details).  
  - Out-of-stock items (with alternatives or restock options).  
- Handles **product inquiries** by retrieving relevant details from a large catalog (100k+ products) without exceeding token limits.  

**Scalable AI Techniques** –  
- Uses **Retrieval-Augmented Generation (RAG)** and **vector stores** for efficient data retrieval.  
- Optimized for **GPT-4o** (OpenAI API) to balance cost and performance.  

## **Technical Implementation**  
- Built with **Python** using **LLM frameworks** (e.g., LangChain).  
- Processes structured inputs from **Google Spreadsheets** (products & emails).  
- Outputs organized results in a **multi-sheet spreadsheet** for easy tracking.  

## **Use Case**  
This system is ideal for **e-commerce, customer support automation, and inventory management**, reducing manual workload while ensuring accurate, AI-driven responses.  

---

### **How It Works**  
1. **Inputs**:  
   - **Product Catalog** (ID, name, category, stock, description, season).  
   - **Email Dataset** (ID, subject, body).  

2. **Outputs**:  
   - **Email Classification Sheet** (`email ID, category`).  
   - **Order Status Sheet** (`email ID, product ID, quantity, status`).  
   - **Order Response Sheet** (`email ID, response`).  
   - **Inquiry Response Sheet** (`email ID, response`).  

3. **AI-Powered Logic**:  
   - **LLM-driven classification & response generation**.  
   - **Smart inventory updates** post-order processing.  
   - **Efficient product search** without full catalog injection.  

