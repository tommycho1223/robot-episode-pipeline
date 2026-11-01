"""Command-line entry point: python -m robodata <command>"""
import argparse
import json
import logging

from .config import settings


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(prog="robodata")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db", help="create tables")
    g = sub.add_parser("generate", help="create fake episodes")
    g.add_argument("-n", type=int, default=300)
    g.add_argument("--defect-rate", type=float, default=0.15)
    sub.add_parser("ingest", help="upload raw episodes and register them")
    sub.add_parser("validate", help="run QC checks on pending episodes")
    sub.add_parser("run-all", help="init-db + generate + ingest + validate")
    args = p.parse_args()

    from . import db, generate, ingest, validate

    if args.cmd in ("init-db", "run-all"):
        db.init_schema()
        print("schema ready")
    if args.cmd == "generate":
        print("generate:", json.dumps(generate.generate(settings.raw_dir, args.n, args.defect_rate)))
    if args.cmd == "run-all":
        print("generate:", json.dumps(generate.generate(settings.raw_dir)))
    if args.cmd in ("ingest", "run-all"):
        print("ingest:", json.dumps(ingest.ingest(settings.raw_dir)))
    if args.cmd in ("validate", "run-all"):
        print("validate:", json.dumps(validate.validate_pending()))


if __name__ == "__main__":
    main()
