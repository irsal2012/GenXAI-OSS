"""Peer-to-peer strategy engine (Domain Service)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Iterable

from genxai.core.agent.base import AgentFactory
from genxai.core.agent.runtime import AgentRuntime
from genxai.llm.factory import LLMProviderFactory

from app.domain.policies.consensus import ConsensusPolicy
from app.domain.policies.termination import TerminationPolicy

logger = logging.getLogger(__name__)


@dataclass
class PeerMessage:
    sender: str
    role: str
    content: str
    timestamp: str
    satisfaction: float
    wants_to_terminate: bool


class StrategyMessageBus:
    """Observer-friendly message bus (Observer pattern)."""

    def __init__(self) -> None:
        self._history: list[dict[str, Any]] = []
        self._subscribers: list[Callable[[dict[str, Any]], Any]] = []

    def subscribe(self, callback: Callable[[dict[str, Any]], Any]) -> None:
        self._subscribers.append(callback)

    async def publish(self, message: dict[str, Any]) -> None:
        self._history.append(message)
        for subscriber in self._subscribers:
            result = subscriber(message)
            if asyncio.iscoroutine(result):
                await result

    def history(self) -> list[dict[str, Any]]:
        return list(self._history)


class P2PStrategyEngine:
    """Domain service running P2P brainstorming rounds."""

    def __init__(
        self,
        peers: Iterable[dict[str, str]],
        consensus_policy: ConsensusPolicy,
        termination_policy: TerminationPolicy,
        message_bus: StrategyMessageBus,
        llm_provider: Any | None = None,
        openai_api_key: str | None = None,
    ) -> None:
        self._peers = list(peers)
        self._consensus_policy = consensus_policy
        self._termination_policy = termination_policy
        self._message_bus = message_bus
        self._llm_provider = llm_provider
        self._openai_api_key = openai_api_key
        self._agent_runtimes = self._build_runtimes()

    def _build_runtimes(self) -> list[AgentRuntime]:
        runtimes: list[AgentRuntime] = []
        for peer in self._peers:
            agent = AgentFactory.create_agent(
                id=peer["id"],
                role=peer["role"],
                goal=peer["goal"],
                backstory=peer["backstory"],
                llm_model=peer.get("llm_model", "gpt-4o-mini"),
                temperature=float(peer.get("temperature", 0.3)),
            )
            runtime = AgentRuntime(
                agent=agent,
                llm_provider=self._llm_provider,
                openai_api_key=self._openai_api_key,
            )
            runtimes.append(runtime)
        return runtimes

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        state = {
            "round": 0,
            "quality_score": 0.0,
            "consensus_score": 0.0,
            "message_history": [],
            "strategy_artifact": {
                "executive_summary": "",
                "strategic_themes": [],
                "ai_initiatives": [],
                "prioritized_roadmap": [],
                "risks_and_mitigations": [],
                "kpis": [],
            },
        }
        state["context_company"] = context.get("company_name")

        while True:
            state["round"] += 1
            round_messages = []
            for runtime in self._agent_runtimes:
                task = self._build_task(context, state)
                response = await runtime.execute(task)
                content = response.get("output", "")
                satisfaction = min(1.0, 0.2 * state["round"])
                wants_to_terminate = satisfaction >= 0.8
                message = PeerMessage(
                    sender=response.get("agent_id", runtime.agent.id),
                    role=runtime.agent.config.role,
                    content=content,
                    timestamp=datetime.now().isoformat(),
                    satisfaction=satisfaction,
                    wants_to_terminate=wants_to_terminate,
                )
                message_payload = message.__dict__
                round_messages.append(message_payload)
                await self._message_bus.publish(message_payload)

            state["message_history"].extend(round_messages)
            self._update_quality(state)
            self._update_consensus(state, round_messages)

            should_stop, reason = self._termination_policy.should_terminate(state)
            if should_stop:
                state["termination_reason"] = reason
                break

        await self._update_strategy_artifact(state, state["message_history"])
        return state

    def _build_task(self, context: dict[str, Any], state: dict[str, Any]) -> str:
        objectives = "\n".join(f"- {obj}" for obj in context.get("objectives", []))
        constraints = "\n".join(f"- {c}" for c in context.get("constraints", []))
        current_round = state.get("round", 1)
        return (
            "You are brainstorming AI strategy based on the following business objectives and constraints.\n"
            f"Objectives:\n{objectives}\n\nConstraints:\n{constraints}\n\n"
            f"Round: {current_round}. Provide strategic themes, initiatives, risks, and KPIs."
        )

    def _update_quality(self, state: dict[str, Any]) -> None:
        state["quality_score"] = min(1.0, state["round"] * 0.2)

    def _update_consensus(self, state: dict[str, Any], messages: list[dict[str, Any]]) -> None:
        votes = [msg.get("wants_to_terminate", False) for msg in messages]
        consensus = self._consensus_policy.consensus_reached(votes)
        state["consensus_score"] = sum(1 for v in votes if v) / max(len(votes), 1)
        if consensus:
            state["termination_reason"] = "Consensus reached"

    async def _update_strategy_artifact(self, state: dict[str, Any], messages: list[dict[str, Any]]) -> None:
        company_name = state.get("context_company", "the organization")
        summary = (
            f"Generated {len(messages)} peer insights in round {state['round']} for {company_name}."
        )

        initiatives = await self._rank_initiatives_with_llm(messages)
        if not initiatives:
            extracted = self._extract_candidate_initiatives(messages)
            ranked = sorted(extracted.items(), key=lambda item: (-item[1]["score"], item[0]))
            top_initiatives = ranked[:3] if ranked else []
            initiatives = [
                {
                    "name": name,
                    "rationale": meta["rationale"],
                    "owner": meta["owner"],
                    "timeline": meta["timeline"],
                    "dependencies": meta["dependencies"],
                }
                for name, meta in top_initiatives
            ]

        themes = [
            {
                "title": "Consensus Use Cases",
                "rationale": "Derived from repeated peer suggestions across agents.",
            }
        ]

        roadmap = [
            {
                "horizon": "Now" if idx == 0 else "Next",
                "initiative": initiative["name"],
                "outcomes": [
                    f"Derived from {initiative['owner']} agent",
                    "Backed by multi-agent consensus",
                ],
            }
            for idx, initiative in enumerate(initiatives)
        ]

        risks = [
            {
                "risk": "Selection bias",
                "mitigation": "Ensure multiple agents agree before prioritizing use cases.",
            },
            {
                "risk": "Limited data",
                "mitigation": "Validate initiatives with stakeholder interviews.",
            },
        ]

        kpis = [
            {
                "name": "Agent consensus ratio",
                "target": ">= 0.6",
                "measurement": "Top use cases mentioned by 60%+ of agents",
            }
        ]

        state["strategy_artifact"] = {
            "executive_summary": summary,
            "strategic_themes": themes,
            "ai_initiatives": initiatives,
            "prioritized_roadmap": roadmap,
            "risks_and_mitigations": risks,
            "kpis": kpis,
        }

    async def _rank_initiatives_with_llm(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not messages:
            return []

        provider = self._llm_provider
        if provider is None:
            provider = LLMProviderFactory.create_provider(
                model="gpt-4o-mini",
                api_key=self._openai_api_key,
                temperature=0.2,
            )

        content_blocks = []
        for message in messages:
            role = message.get("role") or message.get("sender") or "Agent"
            content = (message.get("content") or "").strip()
            if not content:
                continue
            content_blocks.append(f"{role}: {content[:1200]}")

        prompt = (
            "You are an AI strategy analyst. Review the peer agent outputs and return the top 3 "
            "use cases (initiatives) ranked by consensus and business impact. "
            "Return STRICT JSON ONLY with this schema: "
            "{\"initiatives\": [{\"name\": string, \"rationale\": string, \"owner\": string, "
            "\"timeline\": string, \"dependencies\": [string]}]}. "
            "Ensure names are short and actionable.\n\n"
            "Peer outputs:\n"
            + "\n\n".join(content_blocks)
        )

        try:
            response = await provider.generate(prompt=prompt)
            payload = self._safe_parse_json(response.content)
            initiatives = payload.get("initiatives") if isinstance(payload, dict) else None
            if isinstance(initiatives, list):
                normalized = []
                for item in initiatives[:3]:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name", "")).strip()
                    if not name:
                        continue
                    normalized.append(
                        {
                            "name": name,
                            "rationale": str(item.get("rationale", "")).strip(),
                            "owner": str(item.get("owner", "Strategy")).strip() or "Strategy",
                            "timeline": str(item.get("timeline", "Next 6-12 months")).strip(),
                            "dependencies": item.get("dependencies")
                            if isinstance(item.get("dependencies"), list)
                            else ["Data", "Change management"],
                        }
                    )
                return normalized
        except Exception as exc:
            logger.warning("LLM ranking failed: %s", exc)
            return []

        return []

    def _safe_parse_json(self, content: str) -> dict[str, Any]:
        if not content:
            return {}
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.replace("json", "", 1).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start == -1 or end == -1 or end <= start:
                return {}
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                return {}

    def _extract_candidate_initiatives(self, messages: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        candidates: dict[str, dict[str, Any]] = {}
        for message in messages:
            content = message.get("content") or ""
            if not content:
                continue
            bullets = self._extract_initiative_bullets(content)
            for bullet in bullets:
                normalized = self._normalize_title(bullet)
                if not normalized:
                    continue
                entry = candidates.setdefault(
                    normalized,
                    {
                        "score": 0,
                        "rationale": bullet,
                        "owner": message.get("role") or message.get("sender") or "Strategy",
                        "timeline": "Next 6-12 months",
                        "dependencies": ["Data", "Change management"],
                    },
                )
                entry["score"] += 1
        return candidates

    def _extract_initiative_bullets(self, content: str) -> list[str]:
        bullets: list[str] = []
        in_initiatives = False
        for line in content.splitlines():
            cleaned = line.strip()
            if not cleaned:
                continue
            if re.match(r"^#+\s*initiatives", cleaned, re.IGNORECASE):
                in_initiatives = True
                continue
            if re.match(r"^#+\s*(risks|kpis|budget|summary|themes)", cleaned, re.IGNORECASE):
                in_initiatives = False
                continue
            if not in_initiatives:
                continue
            if re.match(r"^(?:[-*]|\d+\.)\s+", cleaned):
                cleaned = re.sub(r"^(?:[-*]|\d+\.)\s+", "", cleaned)
                cleaned = re.sub(r"[*_`]+", "", cleaned).strip()
                if not cleaned:
                    continue
                if re.search(r"budget|cost|estimated|allocation|\$", cleaned, re.IGNORECASE):
                    continue
                if cleaned.lower() in {"initiatives", "risks", "kpis"}:
                    continue
                bullets.append(cleaned)
        return bullets

    def _normalize_title(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip()
        return cleaned[:80]