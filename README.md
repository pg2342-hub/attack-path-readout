# attack-path-readout

[![CI](https://github.com/pg2342-hub/attack-path-readout/actions/workflows/ci.yml/badge.svg)](https://github.com/pg2342-hub/attack-path-readout/actions/workflows/ci.yml)

Demo page: https://pranavgudise.dev/attack-path-readout/ (the weekly readout, every path and its ticket, and the go-live gate for the ticket writer; no install needed)

An autonomous validation platform can confirm which attack paths into a network actually work. The hard part after that is getting each one fixed: the right team has to get a ticket it can act on, anything that reaches a crown-jewel system needs a person to look first, and security leadership needs one readout a week that says what closed and what is stuck.

This repo does that for a made-up large electric utility over a four-week pilot:

1. **Inputs.** 18 assets with owners (`data/assets.csv`) and 12 validated attack paths shaped like a validation platform's output (`data/paths.json`). Every CVE on a path is real and in the CISA Known Exploited Vulnerabilities catalog; exploit likelihood comes from FIRST EPSS (`scripts/refresh_feeds.py`).
2. **Ticket agent.** One Claude call per path (`readout/agents.py`, structured output) writes the ticket: which step to fix, the owner's fix steps from the KEV required action, how to verify, and one line for executives.
3. **Guardrails.** Rules (`readout/guardrails.py`) decide whether a ticket can be assigned on its own. Any path that ends at a crown-jewel asset, any CVE that is not on the path, and anything that reads like attack detail sends the ticket to a person, with the reason. Severity is set by rule, not by the model.
4. **Issues.** Assignable tickets open as GitHub issues labelled by team; held tickets get `needs-review` (`readout/issues.py`).
5. **Readout.** Retests and time to close per path and per team (`readout/metrics.py`), and a weekly summary for the CISO written by Claude from the metrics only. A rule checks that every number in it appears in the metrics (`readout/summary.py`).
6. **Gate.** [golive-gate](https://github.com/pg2342-hub/golive-gate) grades each ticket as the agent wrote it, before the guardrails, on 9 checks (3 critical) over 3 runs. A rules-only baseline and a naive router are graded the same way; CI fails if the naive router is ever not blocked.

Scope is staged the way a careful pilot would run it: days 1 to 13 cover internet-facing assets only, and the corporate network is added from day 14.

## Run it

```
pip install anthropic golive-gate
python3 -m unittest                                   # no key needed
python3 -m readout.run --agent template --out runs/template
export ANTHROPIC_API_KEY=...
python3 -m readout.run --agent claude --runs 3 --out runs/mine --summaries
PYTHONPATH=. golive run eval/golive.naive.yml        # the control, blocked
```

The `Record live run` workflow runs the agent with the repo secret `ANTHROPIC_API_KEY`, grades it, opens the issues, rebuilds `docs/` and publishes the page.

## Data

The utility, its assets, owners, attack paths, evidence and timeline are synthetic. CVE records are from the public CISA KEV catalog and scores from FIRST EPSS. No network was tested, and no ticket contains attack steps.
