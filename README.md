# Session-Isolated AI Shopping Assistant

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://ai-shopping-assistant-sv7erzc5wrcp7v853dqksw.streamlit.app/)

An advanced, multi-modal AI Shopping Assistant built with LangChain, Streamlit, and SQLite. The assistant acts as an agentic shopper that can search products, lookup ratings and reviews, isolate order histories and user preferences per browser tab session, perform image-based product recognition, and apply semantic input guardrails.

---

## Key Features

1. **Multi-Modal Product Search**: Upload product images to search for similar items in the store catalog (powered by a Vision LLM to extract product attributes).
2. **ReAct Agent Architecture**: Uses a LangChain reasoning loop to dynamically select tools such as product search, rating retriever, checkout, and order history queries.
3. **Session-Isolated Data Isolation**: Generates a transient `session_id` UUID per browser tab session. All database orders and user preferences are segmented to prevent data leakages between separate users or tabs.
4. **Persistent Personalization Engine**: Stores user preferences (such as price budget ceilings or organic-only settings) persistently in SQLite. On every conversation turn, active preferences are summary-injected directly into the system context.
5. **Relevance Guardrails**: Employs a dual-stage sanitization guardrail (fast-path keyword matching combined with semantic classification) to filter out off-topic requests (e.g. poetry, general knowledge) before they consume tokens on the agent graph.

---

## Directory Structure

```text
10_project_shopping_agent/
├── app.py              # Streamlit Web User Interface & session loader
├── shopping_agent.py   # LangChain ReAct agent compiled with SQL tools & guardrails
├── setup_db.py         # Database migrations and catalog populator
├── reviews_api.py      # Reviews API integration helper
├── store.db            # SQLite database containing listings, reviews, orders, preferences
├── .env.template       # Environment variables template
└── README.md           # Project documentation
```

---

## Getting Started

### 1. Prerequisites
* Python 3.10 or higher
* Groq API Key

### 2. Installation
Clone the repository and navigate to the project directory:
```bash
cd 10_project_shopping_agent
```

Create a virtual environment and install dependencies:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install streamlit langchain langchain-groq langgraph python-dotenv
```

### 3. Environment Variables
Create a `.env` file in the root of the project directory and insert your Groq API Key:
```env
GROQ_API_KEY=your_groq_api_key_here
```

### 4. Database Initialization
Run the database setup script to create tables (`products`, `reviews`, `orders`, `user_preferences`) and populate them with the product catalog and mock reviews:
```bash
python setup_db.py
```

### 5. Running the Application
Launch the Streamlit web application:
```bash
streamlit run app.py
```
Open the provided local URL (typically `http://localhost:8501`) in your browser to interact with the shopping assistant.

---

## Database Schema

* **`products`**: Product name, category, price, description, and organic status.
* **`reviews`**: Ratings, reviewer names, and text comments.
* **`orders`**: Record of checked-out products isolated by `session_id`.
* **`user_preferences`**: Key-value store (`organic_only`, `max_price`) isolated by `session_id`.

---

## Example Queries

* **Search**: *"Show me organic honey under $20"*
* **Preferences**: *"Remember that I only buy organic products"* or *"Forget my budget preference"*
* **Checkout**: *"Order product ID 1"* or *"Get me #3"*
* **History**: *"What have I ordered before?"*

---

## Deployment to Streamlit Community Cloud

To deploy this application to **Streamlit Community Cloud** (free hosting):

1. **GitHub Setup**: Ensure you have pushed the repository to GitHub (we have pushed it to [sarthakgupta99/AI-Shopping-Assistant](https://github.com/sarthakgupta99/AI-Shopping-Assistant)).
2. **Deploy on Streamlit**:
   * Navigate to [share.streamlit.io](https://share.streamlit.io/) and log in with your GitHub account.
   * Click **New app** (or **Create app**).
   * Select your repository `sarthakgupta99/AI-Shopping-Assistant`, branch `main`, and main file path `app.py`.
3. **Configure Environment Variables**:
   * Under the deploy options, click on **Advanced settings**.
   * In the **Secrets** section, configure your Groq API Key using TOML format:
     ```toml
     GROQ_API_KEY = "gsk_..."
     ```
   * Click **Save**.
4. **Launch**: Click **Deploy**. Streamlit will install the dependencies from `requirements.txt` and automatically initialize the database on startup!

