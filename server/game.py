import random
import threading
import time

from server.config import (
    MATCH_DURATION_SECONDS,
    MAX_CONCURRENT_WORDS,
    REPLENISH_LOW_WATER,
    TICK_INTERVAL_SECONDS,
    WORDS_PER_MATCH,
)
from shared.words import generate_word_set


class Match:
    def __init__(self, match_id, duration, word_set, words_remaining, start_time, status="in_progress"):
        self.id = match_id
        self.duration = duration
        self.word_set = word_set
        self.words_remaining = words_remaining
        self.start_time = start_time
        self.status = status
        # user_id -> {username, score, connected, handler, rematch_vote}
        self.players = {}

    def time_left(self) -> float:
        return max(0.0, self.duration - (time.time() - self.start_time))

    def to_state_dict(self) -> dict:
        return {
            "match_id": self.id,
            "words_remaining": list(self.words_remaining),
            "time_left": round(self.time_left(), 1),
            "scores": {p["username"]: p["score"] for p in self.players.values()},
        }


class GameManager:
    """Owns all in-memory game state and mirrors it into the database so a
    server restart or a client reconnect never loses progress.
    """

    def __init__(self, db):
        self.db = db
        self.lock = threading.RLock()
        self.matches = {}          # match_id -> Match
        self.waiting = []          # list of (user_id, handler)
        self.handlers_by_user = {}  # user_id -> handler (current live connection)
        self.usernames = {}        # user_id -> username
        self._load_matches_from_db()

    # ------------------------------------------------------------------
    # startup recovery
    # ------------------------------------------------------------------
    def _load_matches_from_db(self):
        import json

        for row in self.db.get_in_progress_matches():
            match_id = row["id"]
            word_set = json.loads(row["word_set"])
            words_remaining = json.loads(row["words_remaining"])
            m = Match(match_id, row["duration"], word_set, words_remaining, row["start_time"])
            if m.time_left() <= 0:
                self.db.finish_match(match_id)
                continue
            for p in self.db.get_match_players(match_id):
                m.players[p["user_id"]] = {
                    "username": p["username"],
                    "score": p["score"],
                    "connected": False,
                    "handler": None,
                    "rematch_vote": bool(p["rematch_vote"]),
                }
            self.matches[match_id] = m

    def start_tick_loop(self):
        def loop():
            while True:
                time.sleep(TICK_INTERVAL_SECONDS)
                self.tick()

        threading.Thread(target=loop, daemon=True).start()

    def tick(self):
        with self.lock:
            for m in list(self.matches.values()):
                if m.status != "in_progress":
                    continue
                if m.time_left() <= 0:
                    self._finish_match(m)
                    continue
                self._replenish_words(m)
                self._broadcast(m, {"type": "state_update", **m.to_state_dict()})

    def _replenish_words(self, m: "Match"):
        """Keep a steady stream of falling words for the whole match instead
        of letting the screen go empty once the initial pool is typed out.
        """
        if m.time_left() <= REPLENISH_LOW_WATER:
            return
        changed = False
        while len(m.words_remaining) < MAX_CONCURRENT_WORDS:
            m.words_remaining.append(random.choice(m.word_set))
            changed = True
        if changed:
            self.db.update_words_remaining(m.id, m.words_remaining)

    # ------------------------------------------------------------------
    # connection lifecycle
    # ------------------------------------------------------------------
    def on_login(self, handler, user_id: int, username: str):
        with self.lock:
            self.handlers_by_user[user_id] = handler
            self.usernames[user_id] = username
            handler.user_id = user_id
            handler.username = username

            active = self.db.get_active_match_for_user(user_id)
            if active and active["id"] in self.matches:
                m = self.matches[active["id"]]
                m.players[user_id]["connected"] = True
                m.players[user_id]["handler"] = handler
                self.db.set_player_connected(m.id, user_id, True)
                handler.send({
                    "type": "match_found",
                    "resume": True,
                    "opponent": self._opponent_username(m, user_id),
                    "duration": m.duration,
                    **m.to_state_dict(),
                })
                self._notify_opponent(m, user_id, {"type": "opponent_reconnected", "username": username})
                return

            self.waiting = [w for w in self.waiting if w[0] != user_id]
            self.waiting.append((user_id, handler))
            handler.send({"type": "waiting_for_opponent"})
            self._try_matchmake()

    def disconnect(self, handler):
        with self.lock:
            user_id = getattr(handler, "user_id", None)
            if user_id is None:
                return
            self.waiting = [w for w in self.waiting if w[0] != user_id]
            if self.handlers_by_user.get(user_id) is handler:
                del self.handlers_by_user[user_id]
            for m in self.matches.values():
                p = m.players.get(user_id)
                if p is not None and p["handler"] is handler:
                    p["connected"] = False
                    p["handler"] = None
                    self.db.set_player_connected(m.id, user_id, False)
                    if m.status == "in_progress":
                        self._notify_opponent(m, user_id, {"type": "opponent_disconnected", "username": p["username"]})

    # ------------------------------------------------------------------
    # matchmaking
    # ------------------------------------------------------------------
    def _try_matchmake(self):
        while len(self.waiting) >= 2:
            pair = self.waiting[:2]
            self.waiting = self.waiting[2:]
            self._start_match(pair)

    def _start_match(self, pair):
        word_set = generate_word_set(WORDS_PER_MATCH)
        start_time = time.time()
        match_id = self.db.create_match(word_set, MATCH_DURATION_SECONDS, start_time)
        m = Match(match_id, MATCH_DURATION_SECONDS, word_set, list(word_set), start_time)
        for user_id, handler in pair:
            username = self.usernames.get(user_id, str(user_id))
            self.db.add_match_player(match_id, user_id)
            self.db.set_player_connected(match_id, user_id, True)
            m.players[user_id] = {
                "username": username, "score": 0, "connected": True,
                "handler": handler, "rematch_vote": False,
            }
        self.matches[match_id] = m
        for user_id, handler in pair:
            handler.send({
                "type": "match_found",
                "resume": False,
                "opponent": self._opponent_username(m, user_id),
                "duration": MATCH_DURATION_SECONDS,
                **m.to_state_dict(),
            })

    def _opponent_username(self, m: Match, user_id: int):
        for uid, p in m.players.items():
            if uid != user_id:
                return p["username"]
        return None

    # ------------------------------------------------------------------
    # gameplay
    # ------------------------------------------------------------------
    def claim_word(self, match_id: int, user_id: int, word: str):
        with self.lock:
            m = self.matches.get(match_id)
            if not m or m.status != "in_progress" or user_id not in m.players:
                return
            if m.time_left() <= 0:
                self._finish_match(m)
                return
            word = (word or "").strip().lower()
            if not word or word not in m.words_remaining:
                return
            m.words_remaining.remove(word)
            m.players[user_id]["score"] += 1
            self.db.update_words_remaining(match_id, m.words_remaining)
            self.db.update_player_score(match_id, user_id, m.players[user_id]["score"])
            self._broadcast(m, {
                "type": "word_claimed",
                "word": word,
                "by": m.players[user_id]["username"],
                **m.to_state_dict(),
            })

    def rematch_vote(self, match_id: int, user_id: int):
        with self.lock:
            m = self.matches.get(match_id)
            if not m or m.status != "finished" or user_id not in m.players:
                return
            m.players[user_id]["rematch_vote"] = True
            self.db.set_player_rematch_vote(match_id, user_id, True)
            self._notify_opponent(m, user_id, {"type": "opponent_wants_rematch"})
            if len(m.players) >= 2 and all(p["rematch_vote"] for p in m.players.values()):
                self._restart_match(m, reason="rematch")

    def _restart_match(self, m: Match, reason: str):
        word_set = generate_word_set(WORDS_PER_MATCH)
        start_time = time.time()
        m.word_set = word_set
        m.words_remaining = list(word_set)
        m.start_time = start_time
        m.status = "in_progress"
        for p in m.players.values():
            p["score"] = 0
            p["rematch_vote"] = False
        self.db.restart_match(m.id, word_set, start_time)
        self._broadcast(m, {
            "type": "rematch_start",
            "reason": reason,
            "duration": m.duration,
            **m.to_state_dict(),
        })

    def _finish_match(self, m: Match):
        if m.status != "in_progress":
            return
        m.status = "finished"
        self.db.finish_match(m.id)
        scores = {p["username"]: p["score"] for p in m.players.values()}
        best = max(scores.values()) if scores else 0
        winners = [u for u, s in scores.items() if s == best]
        for p in m.players.values():
            if len(winners) != 1:
                result = "draw"
            else:
                result = "win" if p["username"] == winners[0] else "lose"
            if p["connected"] and p["handler"] is not None:
                self._safe_send(p["handler"], {"type": "match_end", "result": result, "scores": scores})

    # ------------------------------------------------------------------
    # admin
    # ------------------------------------------------------------------
    def reset_all(self):
        with self.lock:
            for m in list(self.matches.values()):
                if any(p["connected"] for p in m.players.values()):
                    self._restart_match(m, reason="admin_reset")
                else:
                    if m.status == "in_progress":
                        self.db.finish_match(m.id)
                    del self.matches[m.id]
            self.waiting.clear()

    def get_status_snapshot(self) -> dict:
        with self.lock:
            matches_info = []
            for m in self.matches.values():
                matches_info.append({
                    "id": m.id,
                    "status": m.status,
                    "players": [
                        {"username": p["username"], "score": p["score"], "connected": p["connected"]}
                        for p in m.players.values()
                    ],
                    "word_pool": list(m.word_set),
                    "words_remaining": list(m.words_remaining),
                    "time_left": round(m.time_left(), 1) if m.status == "in_progress" else 0,
                })
            return {
                "connected_count": len(self.handlers_by_user),
                "connected_usernames": [self.usernames.get(uid, str(uid)) for uid in self.handlers_by_user],
                "waiting_count": len(self.waiting),
                "matches": matches_info,
            }

    # ------------------------------------------------------------------
    @staticmethod
    def _broadcast(m: Match, message: dict):
        for p in m.players.values():
            if p["connected"] and p["handler"] is not None:
                GameManager._safe_send(p["handler"], message)

    @staticmethod
    def _notify_opponent(m: Match, user_id: int, message: dict):
        for uid, p in m.players.items():
            if uid != user_id and p["connected"] and p["handler"] is not None:
                GameManager._safe_send(p["handler"], message)

    @staticmethod
    def _safe_send(handler, message: dict):
        try:
            handler.send(message)
        except OSError:
            pass
