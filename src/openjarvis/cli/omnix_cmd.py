"""``jarvis omnix`` — Jarvis OMNIX Workbench v1 commands."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click


@click.group(help="Jarvis OMNIX Workbench v1 — All-in-one OMNIX upgrade coordination")
def omnix() -> None:
    """Jarvis OMNIX Workbench commands."""


@omnix.command()
@click.option("--url", default="http://127.0.0.1:3091/api/jarvis/status-bundle", help="Status bundle URL")
def status(url: str) -> None:
    """Fetch and summarize the OMNIX status bundle."""
    _run_workbench(["status", "--url", url])


@omnix.command()
@click.argument("objective")
@click.option("--url", default="http://127.0.0.1:3091/api/jarvis/status-bundle", help="Status bundle URL")
def plan(objective: str, url: str) -> None:
    """Produce a Jarvis-led OMNIX upgrade plan."""
    _run_workbench(["plan", "--url", url, objective])


@omnix.command()
@click.argument("objective")
@click.option("--url", default="http://127.0.0.1:3091/api/jarvis/status-bundle", help="Status bundle URL")
def prompt(objective: str, url: str) -> None:
    """Generate a branch-only coding-agent prompt."""
    _run_workbench(["prompt", "--url", url, objective])


@omnix.command()
@click.argument("content")
def review(content: str) -> None:
    """Review a coding-agent report and return ACCEPT/HOLD."""
    _run_workbench(["review", content])


@omnix.command()
@click.argument("content")
def qa(content: str) -> None:
    """List necessary validation gaps from evidence."""
    _run_workbench(["qa", content])


@omnix.command()
@click.argument("content")
def gate(content: str) -> None:
    """Release-gatekeeper ACCEPT/HOLD decision."""
    _run_workbench(["gate", content])


@omnix.command()
@click.argument("command")
@click.argument("args", nargs=-1)
def memory(command: str, args: tuple[str, ...]) -> None:
    """Memory system for continuity and decisions."""
    _run_workbench(["memory", command] + list(args))


@omnix.command()
@click.argument("command")
@click.argument("args", nargs=-1)
def artifact(command: str, args: tuple[str, ...]) -> None:
    """Artifact context for documents."""
    _run_workbench(["artifact", command] + list(args))


@omnix.command()
@click.argument("objective")
@click.option("--url", default="http://127.0.0.1:3091/api/jarvis/status-bundle", help="Status bundle URL")
def run(objective: str, url: str) -> None:
    """Orchestrate status→plan→prompt→gate workflow."""
    _run_workbench(["run", "--url", url, objective])


@omnix.command()
@click.argument("command")
def slack(command: str) -> None:
    """Slack status and test-send."""
    _run_workbench(["slack", command])


@omnix.command()
@click.argument("target", nargs=-1, default=None)
def deploy(target: tuple[str, ...] | None) -> None:
    """Deploy readiness check only."""
    args = ["deploy"]
    if target:
        args.extend(target)
    _run_workbench(args)


def _run_workbench(args: list[str]) -> None:
    """Run the omnix workbench script with given arguments."""
    workbench_path = Path(__file__).parent.parent.parent / "scripts" / "omnix-workbench"
    
    if not workbench_path.exists():
        click.echo(f"Error: Workbench script not found at {workbench_path}", err=True)
        sys.exit(1)
    
    result = subprocess.run(
        [str(workbench_path)] + args,
        capture_output=False,
        text=True,
    )
    
    sys.exit(result.returncode)
