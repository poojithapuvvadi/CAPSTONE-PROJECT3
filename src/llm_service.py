"""
LLM Service for AI IT Support Assistant

Provides LLM-based intent detection and response generation.
Supports both OpenAI (GPT) and Anthropic (Claude).
"""

from __future__ import annotations

import json
import os
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
import logging
import src.logging_config  # ensure logging configured

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self, provider: Literal["openai", "anthropic"] = "openai"):
        """Initialize LLM service with specified provider.

        Args:
            provider: "openai" or "anthropic"

        Environment variables required:
            - OPENAI_API_KEY (for OpenAI)
            - ANTHROPIC_API_KEY (for Anthropic)
        """
        self.provider = provider

        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.error("OPENAI_API_KEY environment variable not set")
                raise ValueError("OPENAI_API_KEY environment variable not set")
            self.llm = ChatOpenAI(
                model="gpt-4-turbo",
                temperature=0.3,
                api_key=api_key,
            )
            logger.info("Initialized OpenAI LLM (gpt-4-turbo)")
        elif provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                logger.error("ANTHROPIC_API_KEY environment variable not set")
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")
            self.llm = ChatAnthropic(
                model="claude-3-5-sonnet-20241022",
                temperature=0.3,
                api_key=api_key,
            )
            logger.info("Initialized Anthropic LLM (claude)")
        else:
            logger.error("Unknown LLM provider requested: %s", provider)
            raise ValueError(f"Unknown provider: {provider}")

    def detect_intent(self, user_input: str) -> str:
        """Detect user intent from natural language input using LLM.

        Args:
            user_input: User's message

        Returns:
            Intent string (e.g., 'knowledge_search', 'ticket_create', etc.)
        """
        system_prompt = """You are an IT support triage agent. Analyze the user's message and determine their intent.

Return only the intent keyword, nothing else. Valid intents are:
- knowledge_search (asking how to do something / troubleshooting)
- employee_lookup (asking about employee profile)
- system_status (checking system/service health)
- ticket_lookup (checking status of existing ticket)
- ticket_create (reporting a problem / creating new ticket)
- ticket_update (updating ticket status)
- ticket_history (viewing ticket history/timeline)
- ticket_comment (adding comment to a ticket)
- admin_dashboard (admin summary and analytics)
- clarify_next_action (user just provided employee ID)

Examples:
- "How do I reset my VPN?" -> knowledge_search
- "Show my employee profile" -> employee_lookup
- "Are the systems up?" -> system_status
- "What is the status of IT-1001?" -> ticket_lookup
- "My laptop is broken, please create a ticket" -> ticket_create
- "Mark IT-1001 as resolved" -> ticket_update
- "Show history for IT-1001" -> ticket_history
- "Add a comment to IT-1001: fixed the issue" -> ticket_comment
- "Show admin dashboard" -> admin_dashboard
- "EMP1024" -> clarify_next_action

User message: {user_input}

Intent:"""

        messages = [
            SystemMessage(
                content="You are a support triage classifier. Respond with only the intent keyword."
            ),
            HumanMessage(content=system_prompt.format(user_input=user_input)),
        ]

        response = self.llm.invoke(messages)
        intent = response.content.strip().lower()
        logger.debug("LLM raw intent response: %s", intent)

        # Clean up response
        for valid_intent in [
            "knowledge_search",
            "employee_lookup",
            "system_status",
            "ticket_lookup",
            "ticket_create",
            "ticket_update",
            "ticket_history",
            "ticket_comment",
            "admin_dashboard",
            "clarify_next_action",
        ]:
            if valid_intent in intent:
                return valid_intent

        return "knowledge_search"

    def generate_sql_query(self, user_query: str, schema: dict[str, list[str]]) -> str:
        """Generate a safe SQLite SELECT statement from a natural-language query.

        Only SELECT statements are allowed; no data mutating operations are permitted.
        """
        schema_json = json.dumps(schema, indent=2)
        prompt = f"""
You are a database query assistant. The SQLite schema is:
{schema_json}

User request: {user_query}

Generate a single SQLite SELECT statement ONLY.
Rules:
- Use only the tables and columns listed in the schema.
- Never use DELETE, INSERT, UPDATE, DROP, ALTER, CREATE, or any non-SELECT statement.
- Return only the SQL, with no markdown fences, no explanation, no comments.
- When possible, use LIKE or LOWER() for case-insensitive text matching.
- Keep the query limited to the needed data.
- Use ORDER BY and LIMIT when helpful.
SQL:
"""
        response = self.llm.invoke([
            SystemMessage(content="Return only valid SQLite SELECT SQL."),
            HumanMessage(content=prompt),
        ])
        sql = str(response.content).strip()
        sql = sql.replace("```sql", "").replace("```", "").strip()
        return sql

    def generate_response(self, tool_result: dict, intent: str, user_input: str) -> str:
        """Generate natural language response from tool result using LLM.

        Args:
            tool_result: Result from the executed tool
            intent: The detected intent
            user_input: Original user input for context

        Returns:
            Natural language response
        """
        system_prompt = """You are a helpful IT support agent. Based on the tool result and user intent, 
generate a friendly, professional response. Be concise but helpful. If there was an error, explain it clearly."""

        user_prompt = f"""
User intent: {intent}
User's question: {user_input}

Tool result:
{json.dumps(tool_result, indent=2)}

Provide a helpful response to the user based on this information. Keep it concise and professional.
"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        response = self.llm.invoke(messages)
        logger.debug("LLM generated response (truncated): %s", (response.content or '')[:200])
        return response.content.strip()


# Default LLM service instance
_llm_service: LLMService | None = None


def get_llm_service(provider: str = "openai") -> LLMService:
    """Get or create the LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService(provider=provider)
    return _llm_service


def set_llm_provider(provider: Literal["openai", "anthropic"]) -> None:
    """Set the LLM provider globally."""
    global _llm_service
    _llm_service = LLMService(provider=provider)
