import base64
import json
import os
import sqlite3
from typing import Optional

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from langchain_core.runnables import RunnableConfig

from reviews_api import get_product_rating

load_dotenv()


DB_PATH = os.path.join(os.path.dirname(__file__), "store.db")

llm = ChatGroq(model="qwen/qwen3-32b", temperature=0)
vision_llm = ChatGroq(model="meta-llama/llama-4-scout-17b-16e-instruct", temperature=0)



# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def search_products(query: str, max_price: Optional[float] = None, is_organic: Optional[bool] = None) -> str:
    """
    Search the product database by keyword (matched against name, description, and category).
    Optionally filter by maximum price and/or organic status.
    Returns a JSON array of matching products, each with: id, name, category, price,
    description, is_organic.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    sql = "SELECT id, name, category, price, description, is_organic FROM products WHERE 1=1"
    params: list = []

    if query:
        sql += " AND (name LIKE ? OR description LIKE ? OR category LIKE ?)"
        like = f"%{query}%"
        params.extend([like, like, like])

    if max_price is not None:
        sql += " AND price <= ?"
        params.append(max_price)

    if is_organic is not None:
        sql += " AND is_organic = ?"
        params.append(1 if is_organic else 0)

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    products = [
        {
            "id":          row[0],
            "name":        row[1],
            "category":    row[2],
            "price":       row[3],
            "description": row[4],
            "is_organic":  bool(row[5]),
        }
        for row in rows
    ]
    return json.dumps(products)


@tool
def get_rating(product_id: int) -> str:
    """
    Get the average customer rating and total review count for a product by its ID.
    Returns a JSON object with: product_id, average_rating, review_count.
    """
    result = get_product_rating(product_id)
    return json.dumps(result)


@tool
def checkout(product_id: int, config: RunnableConfig) -> str:
    """
    Place an order for the given product ID. Saves the order to the database and returns
    a confirmation message with the order ID, product name, and price.
    """
    session_id = config.get("configurable", {}).get("session_id") or config.get("configurable", {}).get("thread_id") or "default_session"
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, price FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return f"Error: product with ID {product_id} not found."

    name, price = row
    cursor.execute(
        "INSERT INTO orders (session_id, product_id, product_name, price) VALUES (?, ?, ?, ?)",
        (session_id, product_id, name, price),
    )

    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return (
        f"Order #{order_id} confirmed! '{name}' has been successfully ordered for ${price:.2f}. "
        f"Your order will arrive in 3-5 business days. Thank you for shopping with us!"
    )


@tool
def get_order_history(config: RunnableConfig) -> str:
    """
    Retrieve the user's order history for this session from the database.
    Returns a JSON array of past orders, each containing order id, product name, price, and ordered_at timestamp.
    """
    session_id = config.get("configurable", {}).get("session_id") or config.get("configurable", {}).get("thread_id") or "default_session"
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, product_name, price, ordered_at FROM orders WHERE session_id = ? ORDER BY ordered_at DESC",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    orders = [
        {
            "id": row[0],
            "product_name": row[1],
            "price": row[2],
            "ordered_at": row[3]
        }
        for row in rows
    ]
    return json.dumps(orders)


@tool
def save_user_preference(key: str, value: str, config: RunnableConfig) -> str:
    """
    Save or update a user preference in the database.
    Supported keys:
    - 'organic_only': set to 'true' if the user prefers organic products, or 'false' otherwise.
    - 'max_price': set to a numeric string (e.g. '20.0') representing the user's maximum price limit.
    Returns a confirmation message.
    """
    session_id = config.get("configurable", {}).get("session_id") or config.get("configurable", {}).get("thread_id") or "default_session"
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO user_preferences (session_id, key, value) VALUES (?, ?, ?)",
        (session_id, key, value)
    )
    conn.commit()
    conn.close()
    return f"Preference '{key}' saved successfully with value '{value}'."


@tool
def delete_user_preference(key: str, config: RunnableConfig) -> str:
    """
    Delete a user preference from the database for this session.
    Returns a confirmation message.
    """
    session_id = config.get("configurable", {}).get("session_id") or config.get("configurable", {}).get("thread_id") or "default_session"
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM user_preferences WHERE session_id = ? AND key = ?",
        (session_id, key)
    )
    conn.commit()
    conn.close()
    return f"Preference '{key}' deleted successfully."


@tool
def get_user_preferences(config: RunnableConfig) -> str:
    """
    Retrieve all stored user preferences from the database for this session.
    Returns a JSON object of current preferences (e.g. {"organic_only": "true", "max_price": "20.0"}).
    """
    session_id = config.get("configurable", {}).get("session_id") or config.get("configurable", {}).get("thread_id") or "default_session"
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT key, value FROM user_preferences WHERE session_id = ?",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    prefs = {row[0]: row[1] for row in rows}
    return json.dumps(prefs)


def get_active_preferences_summary(session_id: str) -> str:
    """
    Get a clean, textual summary of the active user preferences for this session.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_preferences'")
    if not cursor.fetchone():
        conn.close()
        return "No preferences set."

    cursor.execute("SELECT key, value FROM user_preferences WHERE session_id = ?", (session_id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return "No preferences set."

    summary_parts = []
    for key, value in rows:
        if key == "organic_only" and value.lower() == "true":
            summary_parts.append("The user only buys organic products.")
        elif key == "max_price":
            try:
                price = float(value)
                summary_parts.append(f"The user has a maximum budget/price limit of ${price:.2f}.")
            except ValueError:
                summary_parts.append(f"The user's maximum price limit is {value}.")
        else:
            summary_parts.append(f"Preference '{key}': '{value}'.")
    return "\n".join(summary_parts)


def is_shopping_related(message: str) -> bool:
    """
    Verify if a message is shopping-related using the LLM.
    Returns True if safe/conversational, False if off-topic.
    """
    cleaned = message.strip().lower().replace(".", "").replace(",", "").replace("!", "").replace("?", "")
    
    # Fast path for common short greetings, confirmations, and standard conversational terms
    safe_keywords = {
        "hello", "hi", "hey", "yes", "no", "sure", "ok", "okay", "yep", "yea", "yeah",
        "thanks", "thank you", "bye", "goodbye", "help", "clear", "reset", "confirm"
    }
    if cleaned in safe_keywords or len(cleaned.split()) <= 2 and any(w in safe_keywords for w in cleaned.split()):
        return True

    prompt = (
        "You are an input guardrail validator for an AI shopping assistant.\n"
        "Your task is to classify if the user's input is related to shopping, products, orders, order history, "
        "user preferences, or friendly conversational greetings/social acknowledgements (like 'hello', 'hi', 'thank you', 'yes', 'no', 'confirm', 'sure').\n"
        "Input is SAFE if the user is asking to search, buy, view orders, set preferences, greeting the assistant, or answering a question with yes/no/confirm.\n"
        "Strictly reject requests that are completely off-topic (e.g., writing code, telling stories, writing poems, answering general knowledge, weather, news, math problems, etc.).\n"
        "Respond with exactly one word: 'SAFE' if the message is shopping-related or acceptable conversation, "
        "or 'UNSAFE' if it is off-topic.\n\n"
        f"User input: {message}\n"
        "Response:"
    )
    try:
        response = llm.invoke(prompt)
        import re
        content_clean = re.sub(r"<think>.*?</think>", "", response.content, flags=re.DOTALL)
        result = content_clean.strip().upper()
        if "UNSAFE" in result:
            return False
        return "SAFE" in result
    except Exception:
        # Fallback to True so the user isn't blocked if API call fails
        return True


@tool
def describe_product_image(image_path: str) -> str:
    """
    Analyze a product image and return its key attributes as a JSON object.
    Use this when the user uploads a photo of a product they are interested in.
    The returned attributes can be used directly with search_products.
    """
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()

    ext = os.path.splitext(image_path)[1].lower().lstrip(".")
    mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"

    message = HumanMessage(content=[
        {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{image_data}"},
        },
        {
            "type": "text",
            "text": (
                "Look at this product image and extract its key attributes. "
                "Return ONLY a JSON object with these fields:\n"
                "- product_type: what kind of product it is (e.g. honey, olive oil, almonds)\n"
                "- search_query: a short keyword to search for it (e.g. 'honey', 'olive oil')\n"
                "- is_organic: true if the label says organic, false if not, null if unclear\n"
                "- description: one sentence describing the product"
            ),
        },
    ])

    response = vision_llm.invoke([message])
    return response.content


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = create_agent(
    tools=[
        search_products,
        get_rating,
        checkout,
        describe_product_image,
        get_order_history,
        save_user_preference,
        delete_user_preference,
        get_user_preferences
    ],
    model=llm,
    system_prompt=(
        "You are a helpful shopping assistant. Follow these rules strictly.\n\n"
        "IMAGE SEARCH — when the user provides an image path:\n"
        "1. Call describe_product_image with the path to identify the product.\n"
        "2. Use the returned search_query and is_organic to call search_products.\n"
        "3. Continue with the BROWSING flow from step 2 onwards.\n\n"
        "BROWSING — when the user describes what they want to buy:\n"
        "1. Call search_products to find matching items (apply any price/organic filters given).\n"
        "2. For each candidate, call get_rating to retrieve its average rating.\n"
        "3. Filter by the user's minimum rating if specified.\n"
        "4. Present qualifying products as a numbered list. For each item use this exact format "
        "   (plain text, no backticks, no code blocks, no bold, no italic):\n\n"
        "   #<number>. <name> (ID:<product_id>) — $<price> ★<rating> — <organic or non-organic>\n\n"
        "   Add a blank line between each product entry for readability. "
        "   Always include (ID:X) so you can reference it later.\n"
        "5. If only one product qualifies, still show it in the list and ask: "
        "   'Would you like to order it? Just say yes or give me the number.'\n"
        "6. Do NOT call checkout at this stage.\n\n"
        "ORDERING — when the user confirms they want to buy (e.g. 'yes', 'sure', 'go ahead', "
        "'order number 2', 'the first one', 'get me #3'):\n"
        "1. Look at your previous message to find the (ID:X) for the chosen product "
        "   (if only one was listed and the user says 'yes', use that product's ID).\n"
        "2. Call checkout with that product_id (the number from (ID:X)).\n"
        "3. Confirm the order to the user in plain text.\n\n"
        "ORDER HISTORY — when the user asks what they have ordered before:\n"
        "1. Call get_order_history to fetch past orders.\n"
        "2. Present a friendly summary of their previous orders, including product name, price, and when they ordered it.\n\n"
        "USER PREFERENCES:\n"
        "1. You will be provided with the user's active preferences for this session in the system context.\n"
        "2. Respect these preferences (e.g., only organic, maximum price) in all searches unless the user explicitly asks to ignore them.\n"
        "3. If the user explicitly asks you to remember a preference (e.g., 'always prefer organic', 'remember that I don't want items over $20'), call save_user_preference with the appropriate key ('organic_only' or 'max_price') and value.\n"
        "4. If the user asks to remove/forget a preference, call delete_user_preference with the key.\n\n"
        "Never place an order unless the user explicitly confirms. "
        "Never guess a product_id — always take it from the (ID:X) in your own previous message."
    )
)

if __name__ == "__main__":
    # Test execution
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "I want to buy organic honey with 4.5+ rating and less than $20 price."
                    ),
                }
            ]
        },
        config={"configurable": {"session_id": "test_session_id"}}
    )
    print(result["messages"][-1].content)
