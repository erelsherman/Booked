"""Scan evaluation harness. See docs/PROTOTYPE_PLAN.md.

Two stages so the expensive one runs once:
  read   photos -> spine reads (calls a model, costs money, writes JSONL)
  score  reads + ground truth + catalog -> accuracy and cost report (free, repeatable)
"""
