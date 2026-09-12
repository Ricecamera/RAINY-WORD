import random
import time
from collections import Counter

import pygame

from client import config
from client.network import ServerConnection

BG_COLOR = (16, 20, 38)
PANEL_COLOR = (26, 32, 58)
ACCENT = (86, 140, 230)
TEXT_COLOR = (235, 236, 245)
MUTED_COLOR = (140, 145, 170)
GOOD_COLOR = (110, 220, 150)
BAD_COLOR = (235, 95, 95)

PLAY_TOP = 110
PLAY_BOTTOM = config.WINDOW_HEIGHT - 110


class TextInput:
    def __init__(self, rect, font, placeholder="", password=False):
        self.rect = pygame.Rect(rect)
        self.font = font
        self.placeholder = placeholder
        self.password = password
        self.text = ""
        self.active = False

    def handle_event(self, event) -> bool:
        """Returns True if Enter was pressed while this field was active."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_RETURN:
                return True
            elif event.unicode and event.unicode.isprintable():
                self.text += event.unicode
        return False

    def draw(self, surface):
        border = ACCENT if self.active else (70, 75, 100)
        pygame.draw.rect(surface, (10, 13, 26), self.rect, border_radius=6)
        pygame.draw.rect(surface, border, self.rect, 2, border_radius=6)
        shown = ("•" * len(self.text)) if self.password else self.text
        if shown:
            surf = self.font.render(shown, True, TEXT_COLOR)
        else:
            surf = self.font.render(self.placeholder, True, MUTED_COLOR)
        surface.blit(surf, (self.rect.x + 10, self.rect.y + (self.rect.height - surf.get_height()) // 2))


class Button:
    def __init__(self, rect, label, font, color=ACCENT):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.font = font
        self.color = color

    def clicked(self, event) -> bool:
        return event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos)

    def draw(self, surface):
        pygame.draw.rect(surface, self.color, self.rect, border_radius=8)
        surf = self.font.render(self.label, True, (15, 15, 25))
        surface.blit(surf, surf.get_rect(center=self.rect.center))


class FallingWord:
    def __init__(self, text: str):
        self.text = text
        self.x = random.uniform(20, config.WINDOW_WIDTH - 160)
        self.y = random.uniform(PLAY_TOP - 200, PLAY_TOP - 10)
        self.speed = random.uniform(35, 80)

    def update(self, dt: float):
        self.y += self.speed * dt
        if self.y > PLAY_BOTTOM:
            self.y = random.uniform(PLAY_TOP - 150, PLAY_TOP - 10)
            self.x = random.uniform(20, config.WINDOW_WIDTH - 160)


class RainyWordsApp:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Rainy Words")
        self.screen = pygame.display.set_mode((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()

        self.font = pygame.font.SysFont("arial", 22)
        self.font_small = pygame.font.SysFont("arial", 16)
        self.font_big = pygame.font.SysFont("arial", 40, bold=True)
        self.font_word = pygame.font.SysFont("consolas", 22, bold=True)

        self.conn = ServerConnection(config.SERVER_HOST, config.SERVER_PORT)

        self.state = "LOGIN"
        self.mode = "login"  # or "register"
        self.username_input = TextInput((300, 260, 300, 44), self.font, "Username")
        self.password_input = TextInput((300, 320, 300, 44), self.font, "Password", password=True)
        self.login_btn = Button((300, 390, 140, 44), "Log In", self.font)
        self.register_btn = Button((460, 390, 140, 44), "Register", self.font)
        self.status_message = ""
        self.error_message = ""

        self.username = None
        self.match_id = None
        self.opponent = None
        self.scores = {}
        self.time_left = 0.0
        self.falling_words = []
        self.word_input = TextInput((40, config.WINDOW_HEIGHT - 70, config.WINDOW_WIDTH - 80, 48), self.font_word, "Type the falling word and press Enter")
        self.banner = ""
        self.banner_until = 0.0

        self.result = None
        self.rematch_requested = False
        self.opponent_rematch_requested = False
        self.rematch_btn = Button((config.WINDOW_WIDTH // 2 - 100, 420, 200, 50), "Rematch", self.font)

    # ------------------------------------------------------------------
    def run(self):
        try:
            self.conn.connect()
        except OSError as exc:
            self._fatal(f"Could not reach server at {config.SERVER_HOST}:{config.SERVER_PORT}\n({exc})")
            return

        running = True
        while running:
            dt = self.clock.tick(config.FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                else:
                    self._handle_event(event)

            for message in self.conn.poll():
                self._handle_message(message)

            self._update(dt)
            self._draw()
            pygame.display.flip()

        self.conn.close()
        pygame.quit()

    def _fatal(self, message):
        self.screen.fill(BG_COLOR)
        lines = message.split("\n")
        y = config.WINDOW_HEIGHT // 2 - len(lines) * 15
        for line in lines:
            surf = self.font.render(line, True, BAD_COLOR)
            self.screen.blit(surf, surf.get_rect(center=(config.WINDOW_WIDTH // 2, y)))
            y += 30
        pygame.display.flip()
        pygame.time.wait(4000)
        pygame.quit()

    # ------------------------------------------------------------------
    # server -> client
    # ------------------------------------------------------------------
    def _handle_message(self, message: dict):
        msg_type = message.get("type")

        if msg_type == "login_fail":
            self.error_message = message.get("reason", "Login failed.")
        elif msg_type == "register_fail":
            self.error_message = message.get("reason", "Registration failed.")
        elif msg_type == "register_ok":
            self.error_message = ""
        elif msg_type == "login_ok":
            self.username = message.get("username")
            self.error_message = ""
        elif msg_type == "welcome":
            self.status_message = message.get("message", "")
        elif msg_type == "waiting_for_opponent":
            self.state = "WAITING"
        elif msg_type == "match_found":
            self._enter_match(message)
        elif msg_type == "state_update":
            self._apply_state(message)
        elif msg_type == "word_claimed":
            self._apply_state(message)
            who = message.get("by")
            self._set_banner(f'"{message.get("word")}" claimed by {who}!', 1.2)
        elif msg_type == "match_end":
            self.result = message.get("result")
            self.scores = message.get("scores", {})
            self.rematch_requested = False
            self.opponent_rematch_requested = False
            self.state = "RESULT"
        elif msg_type == "rematch_start":
            self._enter_match(message, keep_opponent=True)
            reason = message.get("reason")
            if reason == "admin_reset":
                self._set_banner("The server admin reset this match.", 2.5)
        elif msg_type == "opponent_wants_rematch":
            self.opponent_rematch_requested = True
        elif msg_type == "opponent_disconnected":
            self._set_banner(f"{message.get('username')} disconnected - still playing, they can rejoin any time.", 3.0)
        elif msg_type == "opponent_reconnected":
            self._set_banner(f"{message.get('username')} reconnected!", 2.0)
        elif msg_type == "error":
            self.error_message = message.get("message", "")
        elif msg_type == "_disconnected":
            self.state = "DISCONNECTED"

    def _enter_match(self, message, keep_opponent=False):
        self.match_id = message.get("match_id", self.match_id)
        if not keep_opponent:
            self.opponent = message.get("opponent")
        self.time_left = message.get("time_left", 60)
        self.scores = message.get("scores", {})
        self._sync_falling_words(message.get("words_remaining", []))
        self.state = "PLAYING"
        self.word_input.text = ""

    def _apply_state(self, message):
        if "time_left" in message:
            self.time_left = message["time_left"]
        if "scores" in message:
            self.scores = message["scores"]
        if "words_remaining" in message:
            self._sync_falling_words(message["words_remaining"])

    def _sync_falling_words(self, words_remaining):
        desired = Counter(words_remaining)
        current = Counter(w.text for w in self.falling_words)

        for text, have in list(current.items()):
            want = desired.get(text, 0)
            excess = have - want
            removed = 0
            if excess > 0:
                for w in list(self.falling_words):
                    if removed >= excess:
                        break
                    if w.text == text:
                        self.falling_words.remove(w)
                        removed += 1

        for text, want in desired.items():
            have = sum(1 for w in self.falling_words if w.text == text)
            for _ in range(want - have):
                self.falling_words.append(FallingWord(text))

    def _set_banner(self, text, duration):
        self.banner = text
        self.banner_until = time.time() + duration

    # ------------------------------------------------------------------
    # client -> server / input
    # ------------------------------------------------------------------
    def _handle_event(self, event):
        if self.state == "LOGIN":
            self._handle_login_event(event)
        elif self.state == "PLAYING":
            self._handle_playing_event(event)
        elif self.state == "RESULT":
            self._handle_result_event(event)

    def _handle_login_event(self, event):
        enter_u = self.username_input.handle_event(event)
        enter_p = self.password_input.handle_event(event)
        if enter_u or enter_p:
            self.password_input.active = True
            self.username_input.active = False
        if self.login_btn.clicked(event) or (enter_p and self.mode == "login"):
            self._submit_credentials("login")
        elif self.register_btn.clicked(event):
            self._submit_credentials("register")

    def _submit_credentials(self, mode):
        username = self.username_input.text.strip()
        password = self.password_input.text
        if not username or not password:
            self.error_message = "Enter a username and password."
            return
        self.error_message = ""
        self.conn.send({"type": mode, "username": username, "password": password})

    def _handle_playing_event(self, event):
        if self.word_input.handle_event(event):
            word = self.word_input.text.strip()
            if word:
                self.conn.send({"type": "type_word", "match_id": self.match_id, "word": word})
            self.word_input.text = ""
        self.word_input.active = True

    def _handle_result_event(self, event):
        if self.rematch_btn.clicked(event) and not self.rematch_requested:
            self.rematch_requested = True
            self.conn.send({"type": "rematch_vote", "match_id": self.match_id})

    # ------------------------------------------------------------------
    def _update(self, dt):
        if self.state == "PLAYING":
            for w in self.falling_words:
                w.update(dt)

    # ------------------------------------------------------------------
    # drawing
    # ------------------------------------------------------------------
    def _draw(self):
        self.screen.fill(BG_COLOR)
        if self.state == "LOGIN":
            self._draw_login()
        elif self.state == "WAITING":
            self._draw_waiting()
        elif self.state == "PLAYING":
            self._draw_playing()
        elif self.state == "RESULT":
            self._draw_result()
        elif self.state == "DISCONNECTED":
            self._draw_disconnected()

    def _draw_login(self):
        title = self.font_big.render("Rainy Words", True, ACCENT)
        self.screen.blit(title, title.get_rect(center=(config.WINDOW_WIDTH // 2, 140)))
        subtitle = self.font_small.render("Log in or register to play", True, MUTED_COLOR)
        self.screen.blit(subtitle, subtitle.get_rect(center=(config.WINDOW_WIDTH // 2, 190)))

        self.username_input.draw(self.screen)
        self.password_input.draw(self.screen)
        self.login_btn.draw(self.screen)
        self.register_btn.draw(self.screen)

        if self.error_message:
            surf = self.font_small.render(self.error_message, True, BAD_COLOR)
            self.screen.blit(surf, surf.get_rect(center=(config.WINDOW_WIDTH // 2, 460)))

    def _draw_waiting(self):
        if self.status_message:
            surf = self.font.render(self.status_message, True, TEXT_COLOR)
            self.screen.blit(surf, surf.get_rect(center=(config.WINDOW_WIDTH // 2, 220)))
        surf = self.font_big.render("Waiting for an opponent...", True, ACCENT)
        self.screen.blit(surf, surf.get_rect(center=(config.WINDOW_WIDTH // 2, 300)))

    def _draw_playing(self):
        my_score = self.scores.get(self.username, 0)
        opp_score = self.scores.get(self.opponent, 0) if self.opponent else 0

        header = pygame.Rect(0, 0, config.WINDOW_WIDTH, PLAY_TOP)
        pygame.draw.rect(self.screen, PANEL_COLOR, header)

        you = self.font.render(f"{self.username}: {my_score}", True, GOOD_COLOR)
        self.screen.blit(you, (30, 20))
        if self.opponent:
            opp = self.font.render(f"{self.opponent}: {opp_score}", True, (255, 210, 120))
            self.screen.blit(opp, opp.get_rect(topright=(config.WINDOW_WIDTH - 30, 20)))

        timer_color = BAD_COLOR if self.time_left <= 10 else TEXT_COLOR
        timer = self.font_big.render(f"{int(self.time_left):02d}s", True, timer_color)
        self.screen.blit(timer, timer.get_rect(center=(config.WINDOW_WIDTH // 2, 55)))

        pygame.draw.line(self.screen, (60, 66, 95), (0, PLAY_BOTTOM), (config.WINDOW_WIDTH, PLAY_BOTTOM), 2)

        for w in self.falling_words:
            surf = self.font_word.render(w.text, True, TEXT_COLOR)
            box = surf.get_rect(topleft=(w.x, w.y)).inflate(16, 10)
            pygame.draw.rect(self.screen, (40, 46, 78), box, border_radius=6)
            self.screen.blit(surf, (box.x + 8, box.y + 5))

        self.word_input.draw(self.screen)

        if self.banner and time.time() < self.banner_until:
            surf = self.font_small.render(self.banner, True, ACCENT)
            self.screen.blit(surf, surf.get_rect(center=(config.WINDOW_WIDTH // 2, PLAY_TOP + 20)))

    def _draw_result(self):
        result_text = {"win": "You Win!", "lose": "You Lost", "draw": "Draw!"}.get(self.result, "Match Over")
        result_color = {"win": GOOD_COLOR, "lose": BAD_COLOR, "draw": ACCENT}.get(self.result, TEXT_COLOR)
        surf = self.font_big.render(result_text, True, result_color)
        self.screen.blit(surf, surf.get_rect(center=(config.WINDOW_WIDTH // 2, 220)))

        y = 280
        for name, score in self.scores.items():
            line = self.font.render(f"{name}: {score}", True, TEXT_COLOR)
            self.screen.blit(line, line.get_rect(center=(config.WINDOW_WIDTH // 2, y)))
            y += 34

        self.rematch_btn.draw(self.screen)
        if self.rematch_requested and not self.opponent_rematch_requested:
            note = self.font_small.render("Waiting for opponent to accept rematch...", True, MUTED_COLOR)
            self.screen.blit(note, note.get_rect(center=(config.WINDOW_WIDTH // 2, 490)))
        elif self.opponent_rematch_requested and not self.rematch_requested:
            note = self.font_small.render("Opponent wants a rematch!", True, ACCENT)
            self.screen.blit(note, note.get_rect(center=(config.WINDOW_WIDTH // 2, 490)))

        if self.banner and time.time() < self.banner_until:
            note = self.font_small.render(self.banner, True, ACCENT)
            self.screen.blit(note, note.get_rect(center=(config.WINDOW_WIDTH // 2, 380)))

    def _draw_disconnected(self):
        surf = self.font_big.render("Disconnected from server", True, BAD_COLOR)
        self.screen.blit(surf, surf.get_rect(center=(config.WINDOW_WIDTH // 2, 280)))
        note = self.font_small.render("Restart the game and log back in - your progress was saved.", True, MUTED_COLOR)
        self.screen.blit(note, note.get_rect(center=(config.WINDOW_WIDTH // 2, 330)))


def main():
    RainyWordsApp().run()


if __name__ == "__main__":
    main()
