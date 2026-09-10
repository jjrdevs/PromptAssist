"""`passist` CLI — Python stdlib + PyYAML + packaging.

Commands (per PLAN.md §3.1):

    passist new <name> --target <repo>
        Register a feature (snake_case name, one target repo).

    passist run <stage> <name>
        Render the stage body and write it to stdout. `stage` = one of
        research | plan | check-plan | build | continue | review-code.

    passist ls
        List registered features (name, target, last-fired).

    passist export <name> [stage ...]
        Write rendered prompts to a directory or stdout (one file per stage).

    passist sync-agent --target <repo> [--tools CLAUDE.md,AGENTS.md]
        Copy the agent rules into per-tool files in the target repo.

    passist bind <stage> <combo> | bind <stage> --clear
        Bind (or disable) a global hotkey. Persists to settings.json.

    passist list-bindings
        Show the currently-effective hotkey table.

Global flags:
    --data-dir DIR    Override the user-state directory.
    --assets-dir DIR  Override the bundled-assets directory.
    --agent-name NAME Override the default agent name (default: Copilot).
    --quiet          Suppress the "copied" footer line.

Exit codes: 0 on success, 1 on user-error, 2 on unexpected exception.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

from passist import __version__
from passist.models import StageOrder
from passist.render import render_stage
from passist.storage import (
    active_feature,
    delete_feature,
    get_feature,
    load_features,
    load_stages,
    mark_fired,
    save_features,
    save_settings,
    upsert_feature,
    load_settings,
    default_config,
)
from passist.hotkeys import (
    DEFAULT_SAFE_FALLBACKS,
    conflict_within,
    normalize_combination,
    parse,
    suggest_safe_fallback,
)
from passist.agent_sync import ALL_TARGETS, sync_agent
from passist.models import Feature

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _apply_data_dir_override(args: argparse.Namespace) -> None:
    if args.data_dir:
        os.environ["PROMPTASSIST_DATA_DIR"] = str(args.data_dir)


def _apply_assets_dir_override(args: argparse.Namespace) -> None:
    if args.assets_dir:
        os.environ["PROMPTASSIST_ASSETS_DIR"] = str(args.assets_dir)


def _agent_name(args: argparse.Namespace) -> str:
    if args.agent_name:
        return args.agent_name
    from passist.storage import load_prompts
    return str((load_prompts().get("defaults") or {}).get("agent_name") or "Copilot")


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def cmd_new(args: argparse.Namespace) -> int:
    from passist.render import normalize_feature_name
    name = normalize_feature_name(args.name)
    if not args.target:
        args.target = os.environ.get("PROMPTASSIST_TARGET_REPO")
    if not args.target:
        print("error: --target is required (repo path)", file=sys.stderr)
        return 1
    target = str(Path(args.target).expanduser().resolve())

    # Upsert the feature: create fresh, or update the target if it already exists.
    feats = load_features()
    existing = next((f for f in feats if f.name == name), None)
    if existing:
        existing.target_repo = target
        existing.extra.setdefault("updated_target", True)
        upsert_feature(existing)
        created = False
        created_at = existing.created
    else:
        existing = Feature.new(name, target)
        upsert_feature(existing)
        created = True
        created_at = existing.created

    # GUI contract: `new --json` emits a single feature object with the exact
    # shape lib.rs::new_feature parses (name, target_repo, created,
    # last_fired_stage, total_fires, active).
    if getattr(args, "json", False):
        import json as _json
        print(_json.dumps({
            "name": name,
            "target_repo": target,
            "created": created_at,
            "last_fired_stage": existing.last_fired_stage,
            "total_fires": existing.total_fires,
            "active": True,
            "created_now": created,
        }, ensure_ascii=False, indent=2))
        return 0

    if created:
        print(f"feature {name}: created (target {target})")
    else:
        print(f"feature {name}: updated target → {target}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    stage_id = args.stage
    if stage_id not in StageOrder:
        print(f"error: unknown stage {stage_id!r}; expected one of {StageOrder}", file=sys.stderr)
        return 1
    name = args.name if args.name and args.name != "-" else None
    feature = get_feature(name) if name else None
    if feature is None:
        # Fall back to the active feature.
        feature = active_feature()
        if feature is None:
            print(f"error: feature {name!r} not found. Use `passist new {name} --target <repo>` first.", file=sys.stderr)
            return 1
        name = feature.name
    target = feature.target_repo
    agent = _agent_name(args)

    stage = next(s for s in load_stages() if s.id == stage_id)
    rendered = render_stage(stage, name, target, agent_name=agent)

    if getattr(args, "json", False):
        import json as _json
        print(_json.dumps({
            "stage": stage_id,
            "stage_name": stage.name,
            "feature": name,
            "target": target,
            "agent_name": agent,
            "text": rendered,
        }, ensure_ascii=False))
    else:
        sys.stdout.write(rendered)
        if not args.quiet:
            print(f"  [passist · stage={stage.name} · feature={name} · target={target}]", file=sys.stderr)
        suffix = f" into {agent}'s prompt box" if agent else ""
        print(f"\n[passist] {stage.name} ({name}): copied to clipboard. Paste{suffix}.",
              file=sys.stderr)
    # Record that the user fired it (for next-stage tracking).
    try:
        mark_fired(name, stage_id)
    except Exception:
        pass
    return 0


def cmd_ls(args: argparse.Namespace) -> int:
    feats = load_features()
    if getattr(args, "json", False):
        import json as _json
        active = active_feature()
        print(_json.dumps({
            "features": [
                {
                    "name": f.name,
                    "target_repo": f.target_repo,
                    "last_fired_stage": f.last_fired_stage,
                    "total_fires": f.total_fires,
                    "created": f.created,
                    "active": (active is not None and active.name == f.name),
                }
                for f in feats
            ]
        }, ensure_ascii=False, indent=2))
        return 0
    if not feats:
        print("no features registered yet. Use `passist new <name> --target <repo>` first.")
        return 0
    print(f"{len(feats)} feature(s):")
    for f in feats:
        active = "· active" if active_feature() and active_feature().name == f.name else ""
        print(f"  · {f.name:30s}  target={f.target_repo}  last-fired={f.last_fired_stage or '—'}  fires={f.total_fires}{active}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    feature = get_feature(args.name) or active_feature()
    if feature is None:
        print(f"error: feature {args.name!r} not found", file=sys.stderr)
        return 1
    stages = load_stages()
    if args.stages:
        bad = [s for s in args.stages if s not in StageOrder]
        if bad:
            print(f"error: unknown stage(s): {bad}; expected one of {StageOrder}", file=sys.stderr)
            return 1
        selected = [s for s in StageOrder if s in set(args.stages)]
    else:
        selected = list(StageOrder)

    out_dir = Path(args.out).expanduser() if args.out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    pieces: list[str] = []
    for stage_id in selected:
        stage = next(s for s in stages if s.id == stage_id)
        rendered = render_stage(stage, feature.name, feature.target_repo, agent_name=_agent_name(args))
        if out_dir:
            (out_dir / f"{feature.name}_{stage.id}.txt").write_text(rendered, encoding="utf-8")
        else:
            pieces.append(rendered)
    # GUI contract: `export --json` returns {feature, stages} where stages is
    # the concatenated rendered text of the selected stages (lib.rs::render_all).
    if getattr(args, "json", False):
        import json as _json
        print(_json.dumps({
            "feature": feature.name,
            "stages": "\n\n---\n\n".join(pieces),
        }, ensure_ascii=False))
        return 0
    # Human-readable stdout: each stage block separated by a divider.
    sep = "\n" + "=" * 60 + "\n"
    print(sep.join(pieces))
    return 0


def cmd_sync_agent(args: argparse.Namespace) -> int:
    target = args.target or (active_feature().target_repo if active_feature() else None)
    if not target:
        print("error: --target required (or set a feature first)", file=sys.stderr)
        return 1
    tools = (args.tools.split(",") if args.tools else list(ALL_TARGETS))
    written = sync_agent(target, tools=tools, create_dirs=not args.no_mkdirs)
    # GUI contract: `sync-agent --json` returns {written: [paths]} where each
    # path is the string representation of a file the sync just wrote
    # (lib.rs::sync_agent).
    if getattr(args, "json", False):
        import json as _json
        print(_json.dumps({
            "target": str(target),
            "written": [str(p) for p in written],
        }, ensure_ascii=False, indent=2))
        return 0
    for p in written:
        print(f"wrote {p}")
    return 0


def cmd_bind(args: argparse.Namespace) -> int:
    stage = args.stage
    if stage not in StageOrder and stage not in {"next", "open-window", "quit"}:
        print(f"error: unknown binding target {stage!r}", file=sys.stderr)
        return 1
    if args.clear:
        combo: str | None = ""   # empty → disabled
    elif args.combo:
        combo = args.combo
    else:
        print("error: provide a combo, or use --clear", file=sys.stderr)
        return 1

    settings = load_settings()
    if settings.get("hotkeys") is None:
        settings["hotkeys"] = {}
    settings["hotkeys"][stage] = combo

    # Normalize + validate (if not clearing).
    if combo not in ("", None):
        canonical = normalize_combination(combo)
        settings["hotkeys"][stage] = canonical

    conflicts = conflict_within(settings["hotkeys"])
    if conflicts:
        print(f"warning: within-set conflict: {conflicts} (the app will surface this too)", file=sys.stderr)
    save_settings(settings)
    print(f"bound {stage} to {combo!r}")
    return 0


def cmd_list_bindings(args: argparse.Namespace) -> int:
    settings = load_settings()
    hk = settings.get("hotkeys") or {}
    stages = load_stages()
    default_by_id = {s.id: s.default_hotkey for s in stages}
    fallback_by_id = {s.id: s.fallback_hotkey for s in stages}
    rows = []
    for s in stages:
        eff = hk.get(s.id)
        if eff in ("", None):
            eff = default_by_id.get(s.id)
        rows.append({
            "stage": s.id,
            "effective": eff or "—",
            "default": default_by_id.get(s.id) or "—",
            "safe_fallback": fallback_by_id.get(s.id) or "—",
        })
    for extra in ("next", "open-window", "quit"):
        eff = hk.get(extra)
        val = eff if eff not in ("", None) else (default_by_id.get(extra) or "—")
        rows.append({
            "stage": extra,
            "effective": val or "—",
            "default": "—",
            "safe_fallback": DEFAULT_SAFE_FALLBACKS.get(extra) or "—",
        })
    if getattr(args, "json", False):
        import json as _json
        print(_json.dumps({
            "bindings": rows,
            "conflicts": conflict_within(hk),
        }, ensure_ascii=False, indent=2))
        return 0
    print(f"{'stage':15s}  {'effective':15s}  {'default':15s}  {'safe fallback':20s}")
    print("-" * 78)
    for r in rows:
        print(f"{r['stage']:15s}  {r['effective']:15s}  {r['default']:15s}  {r['safe_fallback']:20s}")
    conflicts = conflict_within(hk)
    if conflicts:
        print(f"\nwarning: within-set conflict: {conflicts}")
    return 0


def cmd_apply_safe_fallbacks(args: argparse.Namespace) -> int:
    settings = load_settings()
    if settings.get("hotkeys") is None:
        settings["hotkeys"] = {}
    for stage_id, combo in DEFAULT_SAFE_FALLBACKS.items():
        settings["hotkeys"][stage_id] = combo
    save_settings(settings)
    print("applied safe fallbacks (Ctrl+Shift+1..6, Ctrl+Shift+N, Ctrl+Shift+O)")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    import json as _json
    print(_json.dumps(load_settings(), indent=2, ensure_ascii=False))
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    p = save_settings(default_config())
    print(f"settings reset: {p}")
    return 0


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------

def _add_common(sp: argparse.ArgumentParser) -> None:
    """Global flags available on every subparser so `passist run build --json`
    works the same as `passist --json run build`.

    KEY SUBTLETY: these use ``default=argparse.SUPPRESS`` (not ``default=None``).
    Because argparse subparsers *re-parse* and their defaults would otherwise
    clobber a value already set on the main parser (classic bug: the
    ``--data-dir`` set in the GLOBAL position before the subcommand is lost,
    and only the subcommand-position value survives — or vice versa).
    With SUPPRESS, "not present on the subcommand" means "keep whatever the
    main parser already set", so BOTH positions work and the last one wins in
    the usual sense (a value actually passed anywhere is honored).
    """
    sp.add_argument("--data-dir", type=Path, default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    sp.add_argument("--assets-dir", type=Path, default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    sp.add_argument("--agent-name", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    sp.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    sp.add_argument("--quiet", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="passist",
        description="PromptAssist — multi-stage AI prompt runner (Windows-first).",
    )
    p.add_argument("--version", action="version", version=f"passist {__version__}")
    p.add_argument("--data-dir", type=Path, default=None, help="override the user-state dir")
    p.add_argument("--assets-dir", type=Path, default=None, help="override the bundled-assets dir")
    p.add_argument("--agent-name", default=None, help="override the agent-name placeholder (default: Copilot)")
    p.add_argument("--json", action="store_true", default=False,
                   help="emit machine-readable JSON on stdout instead of human-readable text (used by the GUI)")
    p.add_argument("--quiet", action="store_true", default=False, help=argparse.SUPPRESS)

    sub = p.add_subparsers(dest="command")

    # new
    n = sub.add_parser("new", help="register a feature")
    n.add_argument("name")
    n.add_argument("--target", default=None, help="absolute or relative path to the target repo")
    _add_common(n)
    n.set_defaults(func=cmd_new)

    # run
    r = sub.add_parser("run", help="render one stage to stdout")
    r.add_argument("stage", choices=list(StageOrder),
                   help=f"one of {', '.join(StageOrder)}")
    r.add_argument("name", nargs="?", default=None,
                   help="feature (snake_case). If omitted, uses the active feature.")
    _add_common(r)
    r.set_defaults(func=cmd_run)

    # ls
    l = sub.add_parser("ls", help="list registered features")
    _add_common(l)
    l.set_defaults(func=cmd_ls)

    # export
    e = sub.add_parser("export", help="write rendered prompts to files or stdout")
    e.add_argument("name")
    e.add_argument("stages", nargs="*", help="stage ids to export (defaults to all)")
    e.add_argument("--out", default=None, help="output directory (optional)")
    _add_common(e)
    e.set_defaults(func=cmd_export)

    # sync-agent
    s = sub.add_parser("sync-agent", help="write agent_rules.md into per-tool files")
    s.add_argument("--target", default=None)
    s.add_argument("--tools", default=None, help="comma-separated list; default: all 4")
    s.add_argument("--no-mkdirs", action="store_true", help="don't create missing dirs")
    _add_common(s)
    s.set_defaults(func=cmd_sync_agent)

    # bind
    b = sub.add_parser("bind", help="bind a stage to a hotkey combo")
    b.add_argument("stage")
    b.add_argument("combo", nargs="?", default=None, help="new combo, or omit for current value")
    b.add_argument("--clear", action="store_true", help="disable this stage's hotkey (button only)")
    _add_common(b)
    b.set_defaults(func=cmd_bind)

    # list-bindings
    lb = sub.add_parser("list-bindings", help="show the currently-effective hotkey table")
    _add_common(lb)
    lb.set_defaults(func=cmd_list_bindings)

    # apply-safe-fallbacks
    af = sub.add_parser("apply-safe-fallbacks", help="swap all stage hotkeys to the Ctrl+Shift+1..6 set")
    _add_common(af)
    af.set_defaults(func=cmd_apply_safe_fallbacks)

    # show
    sh = sub.add_parser("show", help="dump current settings.json (pretty JSON)")
    _add_common(sh)
    sh.set_defaults(func=cmd_show)

    # reset
    rt = sub.add_parser("reset", help="restore default settings.json")
    _add_common(rt)
    rt.set_defaults(func=cmd_reset)

    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.command:
        build_parser().print_help()
        return 0
    _apply_data_dir_override(args)
    _apply_assets_dir_override(args)
    try:
        return args.func(args)
    except Exception as exc:  # pragma: no cover (test coverage for error paths is in tests/)
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
