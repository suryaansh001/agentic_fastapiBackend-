#!/usr/bin/env python3
"""Probe Laya routing against a matrix of representative prompts.

Prints the classification (route / mode / operation / chart type /
confidence) for each prompt so the criteria and thresholds can be tuned
against the live API.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/laya_probe.py
"""
import asyncio

from app.agent.laya import LayaClassificationError, get_laya_classifier

PROMPTS = [
    "Show me the deals in the pipeline",
    "Create a bar chart of deals by stage",
    "Create a line chart using months = [Jan, Feb, Mar] and values = [12000, -3500, 8200]. Save it as q1_profit",
    "Run python to compute the average deal size",
    "Qualify this lead: VP of Revenue Ops at a 200-person SaaS company",
    "Draft an outreach email to Maya Patel",
    "Who is the CEO of Northstar Analytics?",
    "Hello, what can you do?",
]


async def main() -> None:
    classifier = get_laya_classifier()
    if not classifier.enabled:
        print("LAYA_API_KEY is not configured; nothing to probe.")
        return
    for prompt in PROMPTS:
        try:
            result = await classifier.classify_agent_route(prompt)
            print(f"\n{prompt!r}")
            print(
                "  -> route={} mode={} operation={} chart={} confidence={:.2f}".format(
                    result.route,
                    result.mode,
                    result.operation,
                    result.chart_type,
                    result.confidence,
                )
            )
        except LayaClassificationError as exc:
            print(f"\n{prompt!r}\n  -> ERROR {exc}")
    await classifier.aclose()


if __name__ == "__main__":
    asyncio.run(main())
