import argparse
import time

from server import config
from server.db import Database
from server.game import GameManager
from server.server import RainyWordsServer


def run_headless_status_printer(game_manager, interval=5):
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
        "--headless", action="store_true",
        help="Run without the Tkinter admin GUI and print status to the console instead "
             "(use this on a machine with no display, e.g. inside Docker).",
    )
    args = parser.parse_args()

    db = Database(config.DB_PATH)
    game_manager = GameManager(db)
    game_manager.start_tick_loop()

    server = RainyWordsServer(config.HOST, config.PORT, db, game_manager)
    server.start()
    print(f"Rainy Words server listening on {config.HOST}:{config.PORT}")

    if args.headless:
        run_headless_status_printer(game_manager)
    else:
        from server.admin_gui import AdminGUI
        AdminGUI(game_manager).run()


if __name__ == "__main__":
    main()
