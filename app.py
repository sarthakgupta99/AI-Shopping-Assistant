import os
import tempfile
import uuid

import streamlit as st

from shopping_agent import agent, is_shopping_related, get_active_preferences_summary

# Initialize session_id for isolating user data per session
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="AI Shopping Assistant", page_icon="🛒", layout="wide")

st.title("🛒 AI Shopping Assistant")
st.caption("Tell me what you want — I'll search, rate, and order the best match for you.")

# ---------------------------------------------------------------------------
# Sidebar — shop by image
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Shop by Image")
    st.caption("Upload a photo of a product and I'll find similar items in our store.")


    uploaded_file = st.file_uploader(
        "Upload product image", type=["jpg", "jpeg", "png", "webp"]
    )

    if uploaded_file:
        st.image(uploaded_file, use_container_width=True)

    if uploaded_file and st.button("Find similar products", use_container_width=True):
        suffix = os.path.splitext(uploaded_file.name)[1] or ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.getvalue())
            image_path = tmp.name

        prompt = f"I uploaded a product image. Please analyze it and find similar products in the store. Image path: {image_path}"
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.pending_image = uploaded_file.name
        st.rerun()

# ---------------------------------------------------------------------------
# Chat state
# ---------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# Render history — show a friendlier label for image-search messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user" and msg["content"].startswith("I uploaded a product image"):
            filename = msg["content"].split("Image path:")[-1].strip()
            st.markdown(f"Searching by image: **{os.path.basename(filename)}**")
        else:
            st.markdown(msg["content"].replace("$", r"\$"))

# ---------------------------------------------------------------------------
# Run agent if there's an unprocessed message (image upload triggers this)
# ---------------------------------------------------------------------------
if (
    st.session_state.messages
    and st.session_state.messages[-1]["role"] == "user"
    and "pending_image" in st.session_state
):
    with st.chat_message("assistant"):
        with st.spinner("Analyzing image and searching…"):
            # Inject active preferences for the current session
            pref_summary = get_active_preferences_summary(st.session_state.session_id)
            injected_messages = [
                {
                    "role": "system",
                    "content": (
                        f"CRITICAL SYSTEM CONTEXT:\n"
                        f"{pref_summary}\n"
                        "Always respect these preferences in product searches and filter calculations. "
                        "If a preference limits maximum price or requests organic, ensure you apply "
                        "those filters to your tool calls automatically unless the user explicitly overrides them."
                    )
                }
            ] + st.session_state.messages
            
            result = agent.invoke(
                {"messages": injected_messages},
                config={"configurable": {"session_id": st.session_state.session_id, "thread_id": st.session_state.session_id}}
            )

            import re
            response_raw = result["messages"][-1].content
            response = re.sub(r"<think>.*?</think>", "", response_raw, flags=re.DOTALL).replace("`", "")

        st.markdown(response.replace("$", r"\$"))

    st.session_state.messages.append({"role": "assistant", "content": response})
    del st.session_state.pending_image
    st.rerun()

# ---------------------------------------------------------------------------
# Text input
# ---------------------------------------------------------------------------
if prompt := st.chat_input("e.g. I want organic honey under $15 with 4+ rating"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Input guardrail check
    if not is_shopping_related(prompt):
        response = (
            "I'm sorry, but I can only help you with shopping-related requests "
            "(such as searching for products, checking reviews, viewing your order history, "
            "or placing orders). How can I assist you with your shopping today?"
        )
        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            # Inject active preferences for the current session
            pref_summary = get_active_preferences_summary(st.session_state.session_id)
            injected_messages = [
                {
                    "role": "system",
                    "content": (
                        f"CRITICAL SYSTEM CONTEXT:\n"
                        f"{pref_summary}\n"
                        "Always respect these preferences in product searches and filter calculations. "
                        "If a preference limits maximum price or requests organic, ensure you apply "
                        "those filters to your tool calls automatically unless the user explicitly overrides them."
                    )
                }
            ] + st.session_state.messages

            result = agent.invoke(
                {"messages": injected_messages},
                config={"configurable": {"session_id": st.session_state.session_id, "thread_id": st.session_state.session_id}}
            )
            import re
            response_raw = result["messages"][-1].content
            response = re.sub(r"<think>.*?</think>", "", response_raw, flags=re.DOTALL).replace("`", "")
        st.markdown(response.replace("$", r"\$"))

    st.session_state.messages.append({"role": "assistant", "content": response})

    st.rerun()
