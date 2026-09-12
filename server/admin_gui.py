import tkinter as tk
from tkinter import messagebox


class AdminGUI:
    """Local status window for the game server: connected clients, active
    matches, current word sets, and a reset button. Meant to be viewed on
    the cloud instance's desktop (e.g. over VNC).
    """

    def __init__(self, game_manager, refresh_ms=1000):
        self.game_manager = game_manager
        self.refresh_ms = refresh_ms

        self.root = tk.Tk()
        self.root.title("Rainy Words - Server Admin")
        self.root.geometry("680x520")

        header = tk.Frame(self.root)
        header.pack(fill=tk.X, padx=10, pady=10)

        self.summary_var = tk.StringVar()
        tk.Label(
            header, textvariable=self.summary_var,
            font=("TkDefaultFont", 11, "bold"), justify=tk.LEFT,
        ).pack(side=tk.LEFT)

        tk.Button(
            header, text="Reset All Games", command=self._on_reset,
            bg="#c0392b", fg="white",
        ).pack(side=tk.RIGHT)

        self.text = tk.Text(self.root, state=tk.DISABLED, wrap=tk.WORD, font=("Courier", 10))
        self.text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self._refresh()

    def _on_reset(self):
        if messagebox.askyesno("Reset", "Reset all active games and scores?"):
            self.game_manager.reset_all()
            self._refresh()

    def _refresh(self):
        snapshot = self.game_manager.get_status_snapshot()
        self.summary_var.set(
            f"Connected clients: {snapshot['connected_count']}    "
            f"Waiting for opponent: {snapshot['waiting_count']}"
        )

        lines = ["Connected clients:"]
        if snapshot["connected_usernames"]:
            lines += [f"  - {name}" for name in snapshot["connected_usernames"]]
        else:
            lines.append("  (none)")

        lines += ["", "Matches:"]
        if snapshot["matches"]:
            for m in snapshot["matches"]:
                lines.append(f"  Match #{m['id']} [{m['status']}]  time left: {m['time_left']}s")
                for p in m["players"]:
                    status = "online" if p["connected"] else "offline"
                    lines.append(f"      {p['username']}: {p['score']} pts ({status})")
                lines.append(f"      word pool: {', '.join(m['word_pool'])}")
                falling = ", ".join(m["words_remaining"]) or "(none)"
                lines.append(f"      currently falling: {falling}")
        else:
            lines.append("  (no active matches)")

        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, "\n".join(lines))
        self.text.configure(state=tk.DISABLED)

        self.root.after(self.refresh_ms, self._refresh)

    def run(self):
        self.root.mainloop()
