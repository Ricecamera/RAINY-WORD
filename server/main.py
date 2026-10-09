import argparse
import secrets
import threading
import time

from server import config
from server.db import Database
from server.game import GameManager
from server.server import RainyWordsServer
from server.web_dashboard import DashboardServer


def run_console_status_printer(game_manager, interval=10):
    while True:
        snapshot = game_manager.get_status_snapshot()
        print(
            f"[status] connected={snapshot['connected_count']} "
            f"waiting={snapshot['waiting_count']} matches={len(snapshot['matches'])}"
        )
        for m in snapshot["matches"]:
            players = ", ".join(f"{p['username']}={p['score']}" for p in m["players"])
            print(f"  match #{m['id']} [{m['status']}] time_left={m['time_left']}s players=[{players}]")
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Rainy Words game server")
    parser.add_argument(
        "--print-status", action="store_true",
        help="Also print a periodic status summary to the console "
             "(handy for `docker logs` / `journalctl` alongside the web dashboard).",
    )
    args = parser.parse_args()

    db = Database(config.DB_PATH)
    game_manager = GameManager(db)
    game_manager.start_tick_loop()

    server = RainyWordsServer(config.HOST, config.PORT, db, game_manager)
    server.start()
    print(f"Rainy Words game server listening on {config.HOST}:{config.PORT}")

    admin_password = config.ADMIN_PASSWORD
    if not admin_password:
        admin_password = secrets.token_urlsafe(12)
        print(
            "No RAINY_WORDS_ADMIN_PASSWORD set - generated a one-time admin password "
            f"for this run: {admin_password}\n"
            "Set the RAINY_WORDS_ADMIN_PASSWORD environment variable to keep a stable "
            "password across restarts."
        )

    dashboard = DashboardServer(config.WEB_HOST, config.WEB_PORT, game_manager, config.ADMIN_USERNAME, admin_password)
    dashboard.start()
    print(f"Admin dashboard: http://{config.WEB_HOST}:{config.WEB_PORT}/  (user: {config.ADMIN_USERNAME})")

    if args.print_status:
        run_console_status_printer(game_manager)
    else:
        threading.Event().wait()  # block forever; both servers run on daemon threads


if __name__ == "__main__":
    main()
