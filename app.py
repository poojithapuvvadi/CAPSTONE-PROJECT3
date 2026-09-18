from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

from src.agent import run_agent
from src.data_store import LocalDataStore
import logging
import src.logging_config  # initialize logging for the whole app

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

st.set_page_config(page_title="AI IT Support Assistant", layout="wide")

store = LocalDataStore()
logger.info("Initialized LocalDataStore at %s", store.data_dir)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "agent_state" not in st.session_state:
    st.session_state.agent_state = {"employee_id": "EMP1024", "employee_name": "Priya Nair", "memory": {}}

if "selected_role" not in st.session_state:
    st.session_state.selected_role = "admin"


def refresh_employee_context(employee_id: str | None) -> None:
    employee = store.get_employee(employee_id)
    st.session_state.agent_state["employee_id"] = employee["employee_id"] if employee else None
    st.session_state.agent_state["employee_name"] = employee["name"] if employee else None
    logger.debug("Refreshed employee context: %s -> %s", employee_id, st.session_state.agent_state.get("employee_name"))


st.title("AI IT Support Assistant")
st.caption("Role-aware agentic support assistant with SQL persistence, system health, and ticket lifecycle flows.")

with st.sidebar:
    st.subheader("Session controls")
    selected_employee = st.selectbox(
        "Employee",
        options=[employee["employee_id"] for employee in store.list_employees()],
        index=0,
    )
    selected_role = st.selectbox("Role", ["employee", "admin"], index=0 if st.session_state.selected_role == "employee" else 1)
    st.session_state.selected_role = selected_role
    refresh_employee_context(selected_employee)

    if st.button("Clear chat"):
        st.session_state.chat_history = []
        st.session_state.agent_state = {"employee_id": selected_employee, "employee_name": store.get_employee(selected_employee)["name"], "memory": {}}
        logger.info("Chat cleared for employee %s", selected_employee)
        st.rerun()

    st.markdown("### Demo prompts")
    st.markdown("- How do I reset my VPN password?")
    st.markdown("- What is the status of my ticket?")
    st.markdown("- My VPN is not working. Please raise a ticket.")
    st.markdown("- Please update ticket IT-1001 to resolved.")
    st.markdown("- Show admin dashboard")
    st.markdown("- Add comment to IT-1001: The VPN issue is fixed.")

    employee = store.get_employee(st.session_state.agent_state.get("employee_id"))
    if employee:
        st.success(f"Logged in as {employee['name']} ({employee['role']})")
        logger.info("User logged in: %s (%s)", employee["name"], employee["role"])

    st.subheader("System health")
    for item in store.get_system_status():
        if "operational" in item["status"].lower():
            st.success(f"{item['system_name']} — {item['status']}")
        elif "degraded" in item["status"].lower():
            st.warning(f"{item['system_name']} — {item['status']}")
        else:
            st.error(f"{item['system_name']} — {item['status']}")

chat_tab, admin_tab, recent_tab = st.tabs(["Chat", "Admin Dashboard", "Recent Tickets"])

with admin_tab:
    summary = store.get_dashboard_summary()
    col1, col2, col3 = st.columns(3)
    col1.metric("Open tickets", summary.get("open_ticket_count", 0))
    col2.metric("Resolved", summary.get("ticket_status_counts", {}).get("Resolved", 0))
    col3.metric("In progress", summary.get("ticket_status_counts", {}).get("In Progress", 0))

    st.subheader("System health summary")
    for item in store.get_system_status():
        st.write(f"{item['system_name']}: {item['status']} — {item['notes']}")

with recent_tab:
    recent = store.list_recent_tickets(limit=5)
    for ticket in recent:
        st.markdown(f"**{ticket['ticket_id']}** — {ticket['title']} ({ticket['status']})")
        st.caption(f"Employee: {ticket['employee_id']} | Severity: {ticket['severity']} | Updated: {ticket['updated_at']}")
        st.divider()

with chat_tab:
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("tool_result"):
                with st.expander("Tool result"):
                    st.json(message["tool_result"])

    prompt = st.chat_input("Ask an IT question or request action...")
    if prompt:
        current_state = {
            "user_input": prompt,
            "employee_id": st.session_state.agent_state.get("employee_id"),
            "employee_name": st.session_state.agent_state.get("employee_name"),
            "memory": st.session_state.agent_state.get("memory", {}),
        }

        logger.info("User prompt received: %s", prompt)
        result = run_agent(current_state)
        assistant_reply = result.get("response", "I could not generate a response.")
        tool_result = result.get("tool_result", {})

        st.session_state.chat_history.append({"role": "user", "content": prompt})
        st.session_state.chat_history.append({"role": "assistant", "content": assistant_reply, "tool_result": tool_result})

        st.session_state.agent_state = {
            "employee_id": result.get("employee_id", st.session_state.agent_state.get("employee_id")),
            "employee_name": result.get("employee_name", st.session_state.agent_state.get("employee_name")),
            "memory": result.get("memory", {}),
        }
        logger.debug("Agent updated session state: %s", st.session_state.agent_state)

        with st.chat_message("assistant"):
            st.markdown(assistant_reply)
            if tool_result:
                with st.expander("Tool result"):
                    st.json(tool_result)

        st.rerun()
