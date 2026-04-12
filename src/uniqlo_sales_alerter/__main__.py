"""CLI entry-point for the Uniqlo sales alerter."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Uniqlo Sales Alerter",
    )
    preview_group = parser.add_mutually_exclusive_group()
    preview_group.add_argument(
        "--preview-cli",
        action="store_true",
        help="Run a single check, print deals to the terminal, and exit.",
    )
    preview_group.add_argument(
        "--preview-html",
        action="store_true",
        help="Run a single check, generate an HTML report with images, and open it in the browser.",
    )
    preview_group.add_argument(
        "--preview",
        action="store_true",
        help=argparse.SUPPRESS,  # backward compat alias for --preview-cli
    )
    preview_group.add_argument(
        "--once",
        action="store_true",
        help="Run one production sale check, send configured notifications, and exit.",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to config.yaml (default: config.yaml in project root).",
    )
    args = parser.parse_args()

    if args.preview or args.preview_cli:
        asyncio.run(_run_preview(args.config, mode="cli"))
    elif args.preview_html:
        asyncio.run(_run_preview(args.config, mode="html"))
    elif args.once:
        asyncio.run(_run_once(args.config))
    else:
        _run_server()


async def _run_once(config_path: str | None) -> None:
    from uniqlo_sales_alerter.config import load_config
    from uniqlo_sales_alerter.main import AppState, run_sale_check
    from uniqlo_sales_alerter.notifications.dispatcher import NotificationDispatcher
    from uniqlo_sales_alerter.services.sale_checker import SaleChecker

    config = load_config(config_path)
    checker = SaleChecker(config)
    dispatcher = NotificationDispatcher(config)
    app_state = AppState(config=config, sale_checker=checker, dispatcher=dispatcher)

    try:
        result = await run_sale_check(app_state)
    finally:
        await checker.close()

    print(
        f"  Scanned {result.total_products_scanned} sale items, "
        f"{len(result.matching_deals)} matched your filters, "
        f"{len(result.new_deals)} were new.\n"
    )


async def _run_preview(
    config_path: str | None, *, mode: str,
) -> None:
    from uniqlo_sales_alerter.config import load_config
    from uniqlo_sales_alerter.notifications.base import Notifier
    from uniqlo_sales_alerter.notifications.console import ConsoleNotifier
    from uniqlo_sales_alerter.notifications.html_report import HtmlReportNotifier
    from uniqlo_sales_alerter.services.sale_checker import SaleChecker

    config = load_config(config_path)

    notifier: Notifier
    if mode == "html":
        config.notifications.preview_html = True
        notifier = HtmlReportNotifier(enabled=True)
    else:
        config.notifications.preview_cli = True
        notifier = ConsoleNotifier(enabled=True)

    checker = SaleChecker(config)
    try:
        result = await checker.check()
        await notifier.send(result.matching_deals)
    finally:
        await checker.close()

    print(
        f"  Scanned {result.total_products_scanned} sale items, "
        f"{len(result.matching_deals)} matched your filters.\n"
    )


def _run_server() -> None:
    try:
        import uvicorn
    except ImportError:
        print("uvicorn is required to run the server. Install it with:")
        print("  pip install uvicorn[standard]")
        sys.exit(1)

    uvicorn.run(
        "uniqlo_sales_alerter.main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )


if __name__ == "__main__":
    main()
