# Strategy Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add offline parameter optimization with train/test validation and a CLI report.

**Architecture:** Create `optimizer.py` for candidate generation, train/test splitting, scoring, and result objects. Extend `journal.py` to write optimization reports and `__main__.py` with an `optimize` command.

**Tech Stack:** Python standard library, existing backtester/strategy/config modules, pytest.

---

## Tasks

- [ ] Add failing optimizer tests for split, candidate filtering, training-only selection, and CLI output.
- [ ] Implement optimizer dataclasses and search function.
- [ ] Add optimization journal output.
- [ ] Add `python -m quant_agent optimize`.
- [ ] Run full tests and optimize command.
- [ ] Commit the work.
