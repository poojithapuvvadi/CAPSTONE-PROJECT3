from __future__ import annotations

import os
import re
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from src.data_store import LocalDataStore
from src.llm_service import get_llm_service
import logging
import src.logging_config  # ensure logging is configured

logger = logging.getLogger(__name__)


def _match_employee_id(text: str) -> str | None:
    match = re.search(r"\bEMP\d+\b", text.upper())
    if match:
        return match.group(0).upper()
    return None




def _extract_ticket_id(text: str) -> str | None:
    match = re.search(r"\bIT-\d+\b", text.upper())
    if match:
        return match.group(0).upper()
    return None


def _extract_ticket_status(text: str) -> str | None:
    lowered = text.lower()
    if any(keyword in lowered for keyword in ["resolved", "fixed", "completed"]):
        return "Resolved"
    if any(keyword in lowered for keyword in ["in progress", "working on it", "investigating"]):
        return "In Progress"
    if any(keyword in lowered for keyword in ["closed", "done"]):
        return "Closed"
    if any(keyword in lowered for keyword in ["open", "reopen"]):
        return "Open"
    return None


def _detect_intent(user_input: str) -> str:
    """Detect intent using LLM with fallback to keyword matching."""
    lowered = user_input.lower().strip()

    # Quick fallback for just an employee ID
    if re.fullmatch(r"emp\d+", lowered):
        return "clarify_next_action"

    # Try LLM-based intent detection if API key is available
    llm_provider = os.getenv("LLM_PROVIDER", "openai").lower()
    try:
        logger.debug("Attempting LLM intent detection using provider=%s", llm_provider)
        llm_service = get_llm_service(provider=llm_provider)
        intent = llm_service.detect_intent(user_input)
        logger.debug("LLM detected intent: %s", intent)
        return intent
    except (ValueError, Exception):
        logger.debug("LLM intent detection failed or not available; falling back to keyword matching", exc_info=True)
        # Fallback to keyword-based detection if LLM fails or API key not set
        pass

    # Fallback: keyword-based intent detection (original logic)
    if any(keyword in lowered for keyword in ["admin dashboard", "dashboard", "ticket summary", "recent tickets", "open tickets"]):
        return "admin_dashboard"

    if any(keyword in lowered for keyword in ["ticket history", "show history", "history for ticket", "timeline for ticket"]):
        return "ticket_history"

    if any(keyword in lowered for keyword in ["add comment", "comment on ticket", "leave a note", "update with comment"]):
        return "ticket_comment"

    if any(keyword in lowered for keyword in ["system status", "service status", "health check", "overall status", "are the systems up"]):
        return "system_status"

    if any(keyword in lowered for keyword in ["my profile", "employee profile", "who am i", "employee lookup", "show my employee"]):
        return "employee_lookup"

    if any(keyword in lowered for keyword in ["update ticket", "mark ticket", "resolve ticket", "change status", "close ticket", "set ticket to"]):
        return "ticket_update"

    if any(keyword in lowered for keyword in ["how do i", "how to"]):
        return "knowledge_search"

    if any(keyword in lowered for keyword in ["status of", "check my ticket", "ticket status", "view ticket", "lookup ticket", "existing ticket"]):
        return "ticket_lookup"

    if any(keyword in lowered for keyword in ["raise", "create", "open", "new ticket", "please raise", "submit a ticket", "report an issue"]):
        return "ticket_create"

    if any(keyword in lowered for keyword in ["issue", "problem", "not working", "can't", "failed", "error"]):
        return "ticket_create"

    return "knowledge_search"


def _parse_ticket_details(user_input: str) -> dict[str, str]:
    lowered = user_input.lower()
    category = "General"
    if "vpn" in lowered:
        category = "Network"
    elif "laptop" in lowered:
        category = "Hardware"
    elif "mfa" in lowered or "authentication" in lowered:
        category = "Security"
    elif "email" in lowered:
        category = "Email"

    title = user_input.strip()
    for prefix in [
        "please raise a ticket for ",
        "raise a ticket for ",
        "create a ticket for ",
        "open a ticket for ",
        "please open a ticket for ",
        "i need a ticket for ",
        "need a ticket for ",
        "report an issue with ",
    ]:
        if title.lower().startswith(prefix):
            title = title[len(prefix) :]
            break

    title = title.strip(". ")
    if not title or len(title) < 5:
        title = "IT support request"
    if len(title) > 90:
        title = title[:87] + "..."

    description = user_input.strip()
    return {"title": title, "description": description, "category": category, "severity": "Medium"}


def _extract_comment_text(text: str) -> str:
    if not text:
        return ""

    cleaned = text.strip()
    if ":" in cleaned:
        _, comment = cleaned.split(":", 1)
        comment = comment.strip()
        if comment:
            return comment

    match = re.search(
        r"(?:add\s+comment(?:\s+to)?|comment(?:\s+on)?|leave\s+a\s+note)\s*(?:ticket\s*)?(?:IT-\d+\s*)?(?:[:\-]\s*)?(.*)$",
        cleaned,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()

    return cleaned


class ConversationState(TypedDict, total=False):
    user_input: str
    employee_id: str
    employee_name: str
    intent: str
    pending_field: str
    requires_input: bool
    tool_name: str
    tool_result: dict[str, Any]
    response: str
    memory: dict[str, Any]


class AgentService:
    def __init__(self):
        self.data_store = LocalDataStore()

    def _get_worker_name(self, employee_id: str | None) -> str | None:
        employee = self.data_store.get_employee(employee_id)
        return employee.get("name") if employee else None

    def decision_node(self, state: ConversationState) -> ConversationState:
        incoming = state.get("user_input", "")
        logger.debug("decision_node received input: %s", incoming)
        if not incoming:
            state["response"] = "Please tell me what kind of IT support you need."
            state["requires_input"] = False
            return state

        if re.fullmatch(r"emp\d+", incoming.strip().lower()):
            state["employee_id"] = incoming.strip().upper()
            state["employee_name"] = self._get_worker_name(state["employee_id"]) or state.get("employee_name")
            state["intent"] = "clarify_next_action"
            return state

        employee_id = state.get("employee_id") or _match_employee_id(incoming)
        if employee_id:
            state["employee_id"] = employee_id.upper()
            state["employee_name"] = self._get_worker_name(state["employee_id"]) or state.get("employee_name")

        intent = _detect_intent(incoming)
        state["intent"] = intent

        if intent in {"ticket_lookup", "ticket_create", "ticket_update"} and not state.get("employee_id"):
            ticket_id = _extract_ticket_id(incoming)
            if not ticket_id:
                state["requires_input"] = True
                state["pending_field"] = "employee_id"
                state["response"] = "I can help with that. What is your employee ID?"
                return state

        if intent == "employee_lookup" and not state.get("employee_id"):
            state["requires_input"] = True
            state["pending_field"] = "employee_id"
            state["response"] = "Please share your employee ID so I can look up your profile."
            return state

        if state.get("pending_field") == "employee_id" and state.get("employee_id"):
            state["requires_input"] = False
            state["pending_field"] = ""

        return state

    def route_after_decision(
        self, state: ConversationState
    ) -> Literal[
        "needs_input",
        "knowledge_tool",
        "employee_lookup_tool",
        "system_status_tool",
        "admin_dashboard_tool",
        "ticket_history_tool",
        "ticket_comment_tool",
        "ticket_lookup_tool",
        "ticket_create_tool",
        "ticket_update_tool",
        "clarify_next_action",
        "response_generation",
    ]:
        if state.get("requires_input"):
            return "needs_input"

        intent = state.get("intent", "knowledge_search")
        if intent == "clarify_next_action":
            return "clarify_next_action"
        if intent == "employee_lookup":
            return "employee_lookup_tool"
        if intent == "system_status":
            return "system_status_tool"
        if intent == "admin_dashboard":
            return "admin_dashboard_tool"
        if intent == "ticket_history":
            return "ticket_history_tool"
        if intent == "ticket_comment":
            return "ticket_comment_tool"
        if intent == "ticket_lookup":
            return "ticket_lookup_tool"
        if intent == "ticket_create":
            return "ticket_create_tool"
        if intent == "ticket_update":
            return "ticket_update_tool"
        if intent == "knowledge_search":
            return "knowledge_tool"
        return "response_generation"

    def needs_input_node(self, state: ConversationState) -> ConversationState:
        if state.get("pending_field") == "employee_id":
            state["response"] = "I can help with that. What is your employee ID?"
        else:
            state["response"] = "I need a bit more information before I can proceed."
        return state

    def clarify_next_action_node(self, state: ConversationState) -> ConversationState:
        employee_id = state.get("employee_id")
        employee_name = self._get_worker_name(employee_id)
        if employee_name:
            state["response"] = f"I found your profile for {employee_name}. Would you like me to check your existing tickets, view system status, or raise a new one?"
        else:
            state["response"] = "I found your employee ID, but I could not match it to a profile. Please confirm it and try again."
        return state

    def knowledge_tool_node(self, state: ConversationState) -> ConversationState:
        query = state.get("user_input", "")
        logger.debug("knowledge_tool_node query: %s", query)
        matches = self.data_store.search_knowledge(query)
        state["tool_name"] = "knowledge_search"
        state["tool_result"] = {"articles": matches[:3]}
        return state

    def employee_lookup_tool_node(self, state: ConversationState) -> ConversationState:
        employee_id = state.get("employee_id") or _match_employee_id(state.get("user_input", ""))
        employee = self.data_store.get_employee(employee_id)
        logger.info("employee_lookup for %s -> %s", employee_id, bool(employee))
        state["tool_name"] = "employee_lookup"
        state["tool_result"] = {"success": bool(employee), "employee": employee}
        return state

    def system_status_tool_node(self, state: ConversationState) -> ConversationState:
        query = state.get("user_input", "")
        system_name = None
        if "vpn" in query.lower():
            system_name = "VPN Gateway"
        elif "email" in query.lower():
            system_name = "Corporate Email"
        elif "desktop" in query.lower() or "remote" in query.lower():
            system_name = "Remote Desktop"
        elif "identity" in query.lower() or "login" in query.lower() or "mfa" in query.lower():
            system_name = "Identity Provider"

        if not system_name:
            systems = self.data_store.get_system_status()
        else:
            systems = self.data_store.get_system_status(system_name)
        state["tool_name"] = "system_status"
        state["tool_result"] = {"systems": systems}
        return state

    def admin_dashboard_tool_node(self, state: ConversationState) -> ConversationState:
        employee_id = state.get("employee_id")
        employee_role = self.data_store.get_employee_role(employee_id)
        if employee_role != "admin":
            state["tool_name"] = "admin_dashboard"
            state["tool_result"] = {"success": False, "error": "Access denied. Admin privileges are required."}
            logger.warning("Admin dashboard access denied for %s (role=%s)", employee_id, employee_role)
            return state

        summary = self.data_store.get_dashboard_summary()
        recent_tickets = self.data_store.list_recent_tickets(limit=5)
        state["tool_name"] = "admin_dashboard"
        state["tool_result"] = {"success": True, "summary": summary, "recent_tickets": recent_tickets}
        return state

    def ticket_history_tool_node(self, state: ConversationState) -> ConversationState:
        query = state.get("user_input", "")
        ticket_id = _extract_ticket_id(query) or state.get("memory", {}).get("last_ticket_id")

        if not ticket_id:
            state["tool_name"] = "ticket_history"
            state["tool_result"] = {"success": False, "error": "I need a ticket ID to show the ticket history."}
            return state

        ticket = self.data_store.get_ticket_by_id(ticket_id)
        if not ticket:
            state["tool_name"] = "ticket_history"
            state["tool_result"] = {"success": False, "error": f"Ticket '{ticket_id}' was not found."}
            return state

        history = self.data_store.get_ticket_history(ticket_id)
        comments = self.data_store.get_ticket_comments(ticket_id)
        state["tool_name"] = "ticket_history"
        state["tool_result"] = {"success": True, "ticket": ticket, "history": history, "comments": comments}
        state["memory"] = {**state.get("memory", {}), "last_ticket_id": ticket_id}
        return state

    def ticket_comment_tool_node(self, state: ConversationState) -> ConversationState:
        user_input = state.get("user_input", "")
        employee_id = state.get("employee_id")
        ticket_id = _extract_ticket_id(user_input) or state.get("memory", {}).get("last_ticket_id")
        comment = _extract_comment_text(user_input)

        if not employee_id:
            state["tool_name"] = "ticket_comment"
            state["tool_result"] = {"success": False, "error": "I need your employee ID before I can add a comment."}
            return state

        if not ticket_id:
            state["tool_name"] = "ticket_comment"
            state["tool_result"] = {"success": False, "error": "I need a ticket ID to add your comment."}
            return state

        if not comment:
            state["tool_name"] = "ticket_comment"
            state["tool_result"] = {"success": False, "error": "I could not find a comment in your message."}
            return state

        try:
            created_comment = self.data_store.add_ticket_comment(ticket_id, employee_id, comment)
            state["tool_name"] = "ticket_comment"
            state["tool_result"] = {"success": True, "comment": created_comment}
            state["memory"] = {**state.get("memory", {}), "last_ticket_id": ticket_id}
        except ValueError as exc:
            logger.exception("Failed to add ticket comment for %s by %s: %s", ticket_id, employee_id, exc)
            state["tool_name"] = "ticket_comment"
            state["tool_result"] = {"success": False, "error": str(exc)}
        return state

    def ticket_lookup_tool_node(self, state: ConversationState) -> ConversationState:
        employee_id = state.get("employee_id")
        query = state.get("user_input", "")
        ticket_id = _extract_ticket_id(query)
        lowered_query = query.lower()

        if employee_id and not ticket_id and any(keyword in lowered_query for keyword in ["status of", "status", "what is the status", "current status"]):
            tickets = self.data_store.lookup_tickets(employee_id=employee_id)
        else:
            tickets = self.data_store.lookup_tickets(employee_id=employee_id, query=query, ticket_id=ticket_id)

        state["tool_name"] = "ticket_lookup"
        state["tool_result"] = {"tickets": tickets}
        return state

    def ticket_create_tool_node(self, state: ConversationState) -> ConversationState:
        employee_id = state.get("employee_id")
        if not employee_id:
            state["response"] = "I need your employee ID before I can create a ticket."
            state["tool_result"] = {"success": False, "error": "Unknown employee ID."}
            return state

        details = _parse_ticket_details(state.get("user_input", ""))
        try:
            ticket = self.data_store.create_ticket(
                employee_id=employee_id,
                title=details["title"],
                description=details["description"],
                category=details["category"],
                severity=details["severity"],
            )
            state["tool_name"] = "ticket_create"
            state["tool_result"] = {"success": True, "ticket": ticket}
            state["memory"] = {**state.get("memory", {}), "last_ticket_id": ticket["ticket_id"]}
        except ValueError as exc:
            logger.exception("Ticket creation failed for employee %s: %s", employee_id, exc)
            state["tool_name"] = "ticket_create"
            state["tool_result"] = {"success": False, "error": str(exc)}
        return state

    def ticket_update_tool_node(self, state: ConversationState) -> ConversationState:
        user_input = state.get("user_input", "")
        ticket_id = _extract_ticket_id(user_input) or state.get("memory", {}).get("last_ticket_id")
        status = _extract_ticket_status(user_input)

        if not ticket_id:
            state["tool_name"] = "ticket_update"
            state["tool_result"] = {"success": False, "error": "I need a ticket ID to update the ticket status."}
            return state

        if not status:
            state["tool_name"] = "ticket_update"
            state["tool_result"] = {"success": False, "error": "I could not determine the new status. Please use terms like resolved, in progress, or closed."}
            return state

        try:
            updated_ticket = self.data_store.update_ticket_status(ticket_id, status, note=user_input)
            state["tool_name"] = "ticket_update"
            state["tool_result"] = {"success": True, "ticket": updated_ticket}
            state["memory"] = {**state.get("memory", {}), "last_ticket_id": ticket_id}
        except ValueError as exc:
            logger.exception("Ticket update failed for %s: %s", ticket_id, exc)
            state["tool_name"] = "ticket_update"
            state["tool_result"] = {"success": False, "error": str(exc)}
        return state

    def response_generation_node(self, state: ConversationState) -> ConversationState:
        tool_result = state.get("tool_result") or {}
        intent = state.get("intent", "knowledge_search")
        user_input = state.get("user_input", "")

        # Try LLM-based response generation if available
        llm_provider = os.getenv("LLM_PROVIDER", "openai").lower()
        use_llm = os.getenv("USE_LLM_RESPONSES", "true").lower() == "true"

        if use_llm:
            try:
                logger.debug("Generating response with LLM provider=%s for intent=%s", llm_provider, intent)
                llm_service = get_llm_service(provider=llm_provider)
                state["response"] = llm_service.generate_response(tool_result, intent, user_input)
                if state.get("employee_id"):
                    state["memory"] = {
                        "employee_id": state["employee_id"],
                        "employee_name": state.get("employee_name"),
                    }
                return state
            except (ValueError, Exception):
                logger.exception("LLM response generation failed; falling back to template responses")
                # Fall through to template-based responses
                pass

        # Template-based response fallback
        if intent == "knowledge_search":
            articles = tool_result.get("articles", [])
            if not articles:
                state["response"] = "I could not find a matching IT knowledge article for that request. Please try a different wording or contact the support desk."
            else:
                article = articles[0]
                state["response"] = (
                    f"I found this article: {article['title']}\n"
                    f"Summary: {article['summary']}\n"
                    "This is a retrieved knowledge-base article and may help guide your next step."
                )

        elif intent == "employee_lookup":
            articles = tool_result.get("articles", [])
            if not articles:
                state["response"] = "I could not find a matching IT knowledge article for that request. Please try a different wording or contact the support desk."
            else:
                article = articles[0]
                state["response"] = (
                    f"I found this article: {article['title']}\n"
                    f"Summary: {article['summary']}\n"
                    "This is a retrieved knowledge-base article and may help guide your next step."
                )

        elif intent == "employee_lookup":
            employee = tool_result.get("employee")
            if not employee:
                state["response"] = "I could not find an employee profile for that ID. Please confirm the employee ID and try again."
            else:
                state["response"] = (
                    f"Employee profile:\n"
                    f"- Name: {employee['name']}\n"
                    f"- Employee ID: {employee['employee_id']}\n"
                    f"- Department: {employee['department']}\n"
                    f"- Email: {employee['email']}"
                )

        elif intent == "system_status":
            systems = tool_result.get("systems", [])
            if not systems:
                state["response"] = "I couldn’t find any matching system status records."
            else:
                lines = ["System status:"]
                for system in systems:
                    lines.append(f"- {system['system_name']}: {system['status']} - {system['notes']}")
                state["response"] = "\n".join(lines)

        elif intent == "ticket_lookup":
            tickets = tool_result.get("tickets", [])
            if not tickets:
                state["response"] = "I did not find any matching tickets for that request."
            else:
                lines = ["I found these related tickets:"]
                for ticket in tickets:
                    lines.append(f"- {ticket['ticket_id']}: {ticket['title']} | Status: {ticket['status']} | Severity: {ticket['severity']}")
                state["response"] = "\n".join(lines)

        elif intent == "ticket_create":
            if tool_result.get("success"):
                ticket = tool_result.get("ticket", {})
                state["response"] = (
                    f"Your support ticket has been created successfully.\n"
                    f"Ticket ID: {ticket.get('ticket_id')}\n"
                    f"Title: {ticket.get('title')}\n"
                    "Status: Open"
                )
            else:
                state["response"] = f"I could not create the ticket: {tool_result.get('error', 'Unknown validation error.')}."

        elif intent == "ticket_update":
            if tool_result.get("success"):
                ticket = tool_result.get("ticket", {})
                state["response"] = (
                    f"Ticket {ticket.get('ticket_id')} has been updated successfully.\n"
                    f"New status: {ticket.get('status')}"
                )
            else:
                state["response"] = f"I could not update the ticket: {tool_result.get('error', 'Unknown validation error.')}."

        elif intent == "admin_dashboard":
            if tool_result.get("success"):
                summary = tool_result.get("summary", {})
                recent = tool_result.get("recent_tickets", [])
                lines = ["Admin dashboard:"]
                lines.append(f"- Open tickets: {summary.get('open_ticket_count', 0)}")
                for status_name, count in summary.get("ticket_status_counts", {}).items():
                    lines.append(f"- {status_name}: {count}")
                if recent:
                    lines.append("Recent tickets:")
                    for ticket in recent:
                        lines.append(f"  * {ticket['ticket_id']} | {ticket['title']} | {ticket['status']}")
                state["response"] = "\n".join(lines)
            else:
                state["response"] = f"I could not load the admin dashboard: {tool_result.get('error', 'Access denied')}."

        elif intent == "ticket_history":
            if tool_result.get("success"):
                ticket = tool_result.get("ticket", {})
                history = tool_result.get("history", [])
                comments = tool_result.get("comments", [])
                lines = [f"Ticket history for {ticket.get('ticket_id')}:"]
                for item in history:
                    lines.append(f"- {item['created_at']} | {item['event_type']} | {item['details']}")
                if comments:
                    lines.append("Comments:")
                    for comment in comments:
                        lines.append(f"  * {comment['employee_id']} @ {comment['created_at']}: {comment['comment']}")
                state["response"] = "\n".join(lines)
            else:
                state["response"] = f"I could not retrieve ticket history: {tool_result.get('error', 'Unknown issue')}."

        elif intent == "ticket_comment":
            if tool_result.get("success"):
                result = tool_result.get("comment", {})
                state["response"] = f"Comment added successfully to ticket {result.get('ticket_id')}."
            else:
                state["response"] = f"I could not add the comment: {tool_result.get('error', 'Unknown issue')}."

        else:
            state["response"] = state.get("response") or "I am ready to help with IT support requests."

        if state.get("employee_id"):
            state["memory"] = {
                "employee_id": state["employee_id"],
                "employee_name": state.get("employee_name"),
            }

        return state

    def build_graph(self):
        workflow = StateGraph(ConversationState)
        workflow.add_node("decision", self.decision_node)
        workflow.add_node("needs_input", self.needs_input_node)
        workflow.add_node("knowledge_tool", self.knowledge_tool_node)
        workflow.add_node("employee_lookup_tool", self.employee_lookup_tool_node)
        workflow.add_node("system_status_tool", self.system_status_tool_node)
        workflow.add_node("admin_dashboard_tool", self.admin_dashboard_tool_node)
        workflow.add_node("ticket_history_tool", self.ticket_history_tool_node)
        workflow.add_node("ticket_comment_tool", self.ticket_comment_tool_node)
        workflow.add_node("ticket_lookup_tool", self.ticket_lookup_tool_node)
        workflow.add_node("ticket_create_tool", self.ticket_create_tool_node)
        workflow.add_node("ticket_update_tool", self.ticket_update_tool_node)
        workflow.add_node("response_generation", self.response_generation_node)
        workflow.add_node("clarify_next_action", self.clarify_next_action_node)

        workflow.add_edge(START, "decision")
        workflow.add_conditional_edges(
            "decision",
            self.route_after_decision,
            {
                "needs_input": "needs_input",
                "knowledge_tool": "knowledge_tool",
                "employee_lookup_tool": "employee_lookup_tool",
                "system_status_tool": "system_status_tool",
                "admin_dashboard_tool": "admin_dashboard_tool",
                "ticket_history_tool": "ticket_history_tool",
                "ticket_comment_tool": "ticket_comment_tool",
                "ticket_lookup_tool": "ticket_lookup_tool",
                "ticket_create_tool": "ticket_create_tool",
                "ticket_update_tool": "ticket_update_tool",
                "clarify_next_action": "clarify_next_action",
                "response_generation": "response_generation",
            },
        )
        workflow.add_edge("needs_input", END)
        workflow.add_edge("clarify_next_action", END)
        workflow.add_edge("knowledge_tool", "response_generation")
        workflow.add_edge("employee_lookup_tool", "response_generation")
        workflow.add_edge("system_status_tool", "response_generation")
        workflow.add_edge("admin_dashboard_tool", "response_generation")
        workflow.add_edge("ticket_history_tool", "response_generation")
        workflow.add_edge("ticket_comment_tool", "response_generation")
        workflow.add_edge("ticket_lookup_tool", "response_generation")
        workflow.add_edge("ticket_create_tool", "response_generation")
        workflow.add_edge("ticket_update_tool", "response_generation")
        workflow.add_edge("response_generation", END)

        return workflow.compile()


agent_service = AgentService()
agent_graph = agent_service.build_graph()


def run_agent(state: dict[str, Any]) -> dict[str, Any]:
    logger.debug("run_agent input: %s", state)
    result = agent_graph.invoke(state)
    logger.debug("run_agent result: %s", result)
    return result
