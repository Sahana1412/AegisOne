"""
Execution Agent – executes approved remediation actions through MCP tool adapters.
NEVER executes without explicit approval from ApprovalAgent.
"""
from __future__ import annotations

import logging
from typing import Any

from agents.base_agent import BaseAgent
from band.core.event_bus import BandEvent, BandEventBus
from band.events.event_types import EventType
from db.models import AgentMessage, AuditEntry, Incident
from db.session import AsyncSessionFactory
from sqlalchemy import select

logger = logging.getLogger(__name__)


class ExecutionAgent(BaseAgent):
    name = "execution_agent"
    description = "Executes approved remediation actions via MCP tools. Requires human approval."
    subscribes_to = [EventType.ACTION_APPROVED]
    publishes = [EventType.EXECUTION_COMPLETE, EventType.EXECUTION_FAILED]
    capabilities = [
        "ip_blocking", "account_disabling", "session_revocation",
        "github_issue_creation", "slack_alerting", "process_killing",
    ]

    # MCP tool routing
    TOOL_DISPATCHERS = {
        "block_ip": "_execute_block_ip",
        "disable_account": "_execute_disable_account",
        "kill_process": "_execute_kill_process",
        "revoke_session": "_execute_revoke_session",
        "create_github_issue": "_execute_create_github_issue",
        "send_slack_alert": "_execute_send_slack_alert",
        "quarantine_file": "_execute_quarantine_file",
        "isolate_host": "_execute_isolate_host",
    }

    async def handle_event(self, event: BandEvent) -> None:
        logger.info("ExecutionAgent running approved actions for incident %s", event.incident_id)
        payload = event.payload

        approved_actions = payload.get("approved_actions", [])
        if not approved_actions:
            logger.warning("No actions to execute for incident %s", event.incident_id)
            return

        execution_results = []
        failed_actions = []

        for action in approved_actions:
            result = await self._execute_action(action, event.incident_id)
            if result.get("success"):
                execution_results.append(result)
            else:
                failed_actions.append(result)

            await self._audit_action(event.incident_id, action, result)

        success_count = len(execution_results)
        failure_count = len(failed_actions)

        await self._update_incident_execution(event.incident_id, execution_results, failed_actions)
        await self._save_agent_message(event, execution_results, failed_actions)

        event_type = EventType.EXECUTION_COMPLETE if failure_count == 0 else EventType.EXECUTION_FAILED
        await self.publish(
            event_type=event_type,
            incident_id=event.incident_id,
            payload={
                **payload,
                "execution_results": execution_results,
                "failed_actions": failed_actions,
                "success_count": success_count,
                "failure_count": failure_count,
                "execution_status": "complete" if failure_count == 0 else "partial",
            },
            correlation_id=event.event_id,
        )

    async def _execute_action(self, action: dict[str, Any], incident_id: str) -> dict[str, Any]:
        """Dispatch action to the appropriate MCP tool."""
        action_type = action.get("action_type", "")
        dispatcher_name = self.TOOL_DISPATCHERS.get(action_type)

        if not dispatcher_name:
            return {
                "action_id": action.get("action_id"),
                "action_type": action_type,
                "success": False,
                "error": f"Unknown action type: {action_type}",
                "result": None,
            }

        dispatcher = getattr(self, dispatcher_name, None)
        if not dispatcher:
            return {
                "action_id": action.get("action_id"),
                "action_type": action_type,
                "success": False,
                "error": f"Dispatcher not implemented: {dispatcher_name}",
                "result": None,
            }

        try:
            result = await dispatcher(action, incident_id)
            return {
                "action_id": action.get("action_id"),
                "action_type": action_type,
                "success": True,
                "result": result,
                "error": None,
            }
        except Exception as e:
            logger.exception("Action %s failed: %s", action.get("action_id"), e)
            return {
                "action_id": action.get("action_id"),
                "action_type": action_type,
                "success": False,
                "error": str(e),
                "result": None,
            }

    async def _execute_block_ip(self, action: dict, incident_id: str) -> dict:
        from mcp.abuseipdb.adapter import AbuseIPDBAdapter
        ip = action.get("parameters", {}).get("ip", "")
        if not ip:
            raise ValueError("No IP address provided for block_ip action")
        result = await AbuseIPDBAdapter().report_ip(
            ip=ip,
            categories=[14, 15],  # Hacking, Port Scan
            comment=f"Blocked by AegisOne XDR - Incident {incident_id}",
        )
        return {"ip": ip, "reported": True, "result": result}

    async def _execute_disable_account(self, action: dict, incident_id: str) -> dict:
        params = action.get("parameters", {})
        username = params.get("username", "")
        logger.info("Simulating account disable for user: %s (incident: %s)", username, incident_id)
        return {"username": username, "disabled": True, "method": "simulated"}

    async def _execute_kill_process(self, action: dict, incident_id: str) -> dict:
        params = action.get("parameters", {})
        pid = params.get("pid")
        process_name = params.get("process_name", "unknown")
        logger.info("Simulating process kill: %s (PID: %s)", process_name, pid)
        return {"pid": pid, "process_name": process_name, "killed": True, "method": "simulated"}

    async def _execute_revoke_session(self, action: dict, incident_id: str) -> dict:
        params = action.get("parameters", {})
        session_id = params.get("session_id", "")
        logger.info("Simulating session revocation: %s", session_id)
        return {"session_id": session_id, "revoked": True, "method": "simulated"}

    async def _execute_create_github_issue(self, action: dict, incident_id: str) -> dict:
        from mcp.github.adapter import GitHubAdapter
        params = action.get("parameters", {})
        result = await GitHubAdapter().create_security_issue(
            title=params.get("title", f"Security Incident {incident_id}"),
            body=params.get("body", f"Automated security incident created by AegisOne XDR\n\nIncident ID: {incident_id}"),
            labels=params.get("labels", ["security", "incident"]),
        )
        return result

    async def _execute_send_slack_alert(self, action: dict, incident_id: str) -> dict:
        from mcp.slack.adapter import SlackAdapter
        params = action.get("parameters", {})
        result = await SlackAdapter().send_security_alert(
            channel=params.get("channel", "#security-incidents"),
            incident_id=incident_id,
            message=params.get("message", f"🚨 Security incident detected: {incident_id}"),
            severity=params.get("severity", "high"),
        )
        return result

    async def _execute_quarantine_file(self, action: dict, incident_id: str) -> dict:
        from mcp.filesystem.adapter import FilesystemAdapter
        params = action.get("parameters", {})
        file_path = params.get("file_path", "")
        result = await FilesystemAdapter().quarantine_file(file_path)
        return result

    async def _execute_isolate_host(self, action: dict, incident_id: str) -> dict:
        params = action.get("parameters", {})
        host = params.get("host", "")
        logger.info("Simulating host isolation: %s (incident: %s)", host, incident_id)
        return {"host": host, "isolated": True, "method": "simulated"}

    async def _audit_action(self, incident_id: str, action: dict, result: dict) -> None:
        async with AsyncSessionFactory() as session:
            entry = AuditEntry(
                incident_id=incident_id,
                actor=self.name,
                actor_type="agent",
                action=f"{action.get('action_type', 'unknown')}: {action.get('title', '')}",
                details={
                    "action_id": action.get("action_id"),
                    "parameters": action.get("parameters", {}),
                    "result": result,
                },
                outcome="success" if result.get("success") else "failure",
            )
            session.add(entry)
            await session.commit()

    async def _update_incident_execution(
        self, incident_id: str, results: list, failed: list
    ) -> None:
        async with AsyncSessionFactory() as session:
            res = await session.execute(
                select(Incident).where(Incident.id == incident_id)
            )
            incident = res.scalar_one_or_none()
            if incident:
                incident.execution_result = {
                    "successful": results,
                    "failed": failed,
                    "status": "complete" if not failed else "partial",
                }
                incident.status = "verifying"
                await session.commit()

    async def _save_agent_message(
        self, event: BandEvent, results: list, failed: list
    ) -> None:
        success_list = "\n".join([
            f"✅ {r.get('action_type', '?')}: {r.get('action_id', '')}"
            for r in results
        ])
        fail_list = "\n".join([
            f"❌ {r.get('action_type', '?')}: {r.get('error', 'Unknown error')}"
            for r in failed
        ])

        content = (
            f"**Execution Complete**\n\n"
            f"**Successful Actions ({len(results)}):**\n{success_list or 'None'}\n\n"
        )
        if failed:
            content += f"**Failed Actions ({len(failed)}):**\n{fail_list}\n\n"

        content += "All executed actions have been logged to the audit trail."

        async with AsyncSessionFactory() as session:
            msg = AgentMessage(
                incident_id=event.incident_id,
                agent_name=self.name,
                message_type="execution",
                content=content,
                confidence_score=1.0 if not failed else 0.6,
                extra_data={
                    "success_count": len(results),
                    "failure_count": len(failed),
                },
                band_event_type=event.event_type,
            )
            session.add(msg)
            await session.commit()
