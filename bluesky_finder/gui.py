"""Tkinter GUI for the Bluesky Finder pipeline."""

import logging
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr


class _TkTextHandler(logging.Handler):
    """Logging handler that appends records to a tkinter ScrolledText widget."""

    def __init__(self, widget: scrolledtext.ScrolledText):
        super().__init__()
        self.widget = widget

    def emit(self, record: logging.LogRecord):
        msg = self.format(record) + "\n"
        # Schedule on the main thread to be thread-safe
        self.widget.after(0, self._append, msg)

    def _append(self, msg: str):
        self.widget.config(state="normal")
        self.widget.insert("end", msg)
        self.widget.see("end")
        self.widget.config(state="disabled")


class PipelineGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Bluesky Finder")
        self.root.geometry("920x780")
        self.root.minsize(800, 600)

        self._running = False

        self._build_ui()

    def _build_ui(self):
        # Use a PanedWindow so user can resize config vs output
        pane = ttk.PanedWindow(self.root, orient="vertical")
        pane.pack(fill="both", expand=True, padx=10, pady=10)

        # ===== Top: config + controls =====
        top = ttk.Frame(pane)
        pane.add(top, weight=1)

        self._build_config_panel(top)
        self._build_controls(top)

        # ===== Bottom: output log =====
        bottom = ttk.Frame(pane)
        pane.add(bottom, weight=2)

        self._build_log(bottom)

    # ---------- config panel ----------

    def _build_config_panel(self, parent):
        nb = ttk.Notebook(parent)
        nb.pack(fill="both", expand=True, pady=(0, 4))

        # -- Discovery tab --
        disc = ttk.Frame(nb, padding=8)
        nb.add(disc, text="Discovery")

        ttk.Label(disc, text="Seed Hashtags (comma-separated):").grid(
            row=0, column=0, sticky="w", pady=2
        )
        self.hashtags_var = tk.StringVar()
        ttk.Entry(disc, textvariable=self.hashtags_var, width=70).grid(
            row=0, column=1, sticky="ew", padx=4, pady=2
        )

        ttk.Label(disc, text="Anchor Handles (comma-separated):").grid(
            row=1, column=0, sticky="w", pady=2
        )
        self.anchors_var = tk.StringVar()
        ttk.Entry(disc, textvariable=self.anchors_var, width=70).grid(
            row=1, column=1, sticky="ew", padx=4, pady=2
        )

        ttk.Label(disc, text="Max candidates per hashtag:").grid(
            row=2, column=0, sticky="w", pady=2
        )
        self.max_per_hashtag_var = tk.IntVar()
        ttk.Spinbox(disc, from_=10, to=5000, textvariable=self.max_per_hashtag_var,
                     width=10).grid(row=2, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(disc, text="Max accounts per anchor:").grid(
            row=3, column=0, sticky="w", pady=2
        )
        self.max_per_anchor_var = tk.IntVar()
        ttk.Spinbox(disc, from_=10, to=5000, textvariable=self.max_per_anchor_var,
                     width=10).grid(row=3, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(disc, text="Posts to fetch per candidate:").grid(
            row=4, column=0, sticky="w", pady=2
        )
        self.fetch_posts_var = tk.IntVar()
        ttk.Spinbox(disc, from_=10, to=200, textvariable=self.fetch_posts_var,
                     width=10).grid(row=4, column=1, sticky="w", padx=4, pady=2)

        disc.columnconfigure(1, weight=1)

        # -- Scoring tab --
        scoring = ttk.Frame(nb, padding=8)
        nb.add(scoring, text="Scoring / LLM")

        ttk.Label(scoring, text="Match threshold (overall >= ):").grid(
            row=0, column=0, sticky="w", pady=2
        )
        self.thresh_match_var = tk.DoubleVar()
        ttk.Spinbox(scoring, from_=0.0, to=1.0, increment=0.05,
                     textvariable=self.thresh_match_var, width=10).grid(
            row=0, column=1, sticky="w", padx=4, pady=2
        )

        ttk.Label(scoring, text="Maybe threshold (overall >= ):").grid(
            row=1, column=0, sticky="w", pady=2
        )
        self.thresh_maybe_var = tk.DoubleVar()
        ttk.Spinbox(scoring, from_=0.0, to=1.0, increment=0.05,
                     textvariable=self.thresh_maybe_var, width=10).grid(
            row=1, column=1, sticky="w", padx=4, pady=2
        )

        ttk.Label(scoring, text="OpenRouter model:").grid(
            row=2, column=0, sticky="w", pady=2
        )
        self.model_var = tk.StringVar()
        ttk.Entry(scoring, textvariable=self.model_var, width=40).grid(
            row=2, column=1, sticky="ew", padx=4, pady=2
        )

        ttk.Label(scoring, text="DB path:").grid(
            row=3, column=0, sticky="w", pady=2
        )
        self.db_path_var = tk.StringVar()
        ttk.Entry(scoring, textvariable=self.db_path_var, width=40).grid(
            row=3, column=1, sticky="ew", padx=4, pady=2
        )

        scoring.columnconfigure(1, weight=1)

        # -- TTL tab --
        ttl_tab = ttk.Frame(nb, padding=8)
        nb.add(ttl_tab, text="TTLs (hours)")

        ttk.Label(ttl_tab, text="Profile refresh TTL:").grid(
            row=0, column=0, sticky="w", pady=2
        )
        self.ttl_profile_var = tk.IntVar()
        ttk.Spinbox(ttl_tab, from_=1, to=720, textvariable=self.ttl_profile_var,
                     width=10).grid(row=0, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(ttl_tab, text="Posts refresh TTL:").grid(
            row=1, column=0, sticky="w", pady=2
        )
        self.ttl_posts_var = tk.IntVar()
        ttk.Spinbox(ttl_tab, from_=1, to=720, textvariable=self.ttl_posts_var,
                     width=10).grid(row=1, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(ttl_tab, text="LLM eval refresh TTL:").grid(
            row=2, column=0, sticky="w", pady=2
        )
        self.ttl_llm_var = tk.IntVar()
        ttk.Spinbox(ttl_tab, from_=1, to=720, textvariable=self.ttl_llm_var,
                     width=10).grid(row=2, column=1, sticky="w", padx=4, pady=2)

        # Load current config values into the widgets
        self._load_config_into_ui()

    def _load_config_into_ui(self):
        """Read current AppConfig and populate the GUI fields."""
        try:
            from .config import settings
            self.hashtags_var.set(", ".join(settings.seed_hashtags))
            self.anchors_var.set(", ".join(settings.anchor_handles))
            self.max_per_hashtag_var.set(settings.discovery_limits.max_candidates_per_hashtag)
            self.max_per_anchor_var.set(settings.discovery_limits.max_accounts_per_anchor)
            self.fetch_posts_var.set(settings.fetch_posts_limit)
            self.thresh_match_var.set(settings.scoring_thresholds.match_overall)
            self.thresh_maybe_var.set(settings.scoring_thresholds.maybe_overall)
            self.model_var.set(settings.openrouter_model)
            self.db_path_var.set(str(settings.db_path))
            self.ttl_profile_var.set(settings.ttl_profile_hours)
            self.ttl_posts_var.set(settings.ttl_posts_hours)
            self.ttl_llm_var.set(settings.ttl_llm_hours)
        except Exception as e:
            # Config may fail if env vars are missing; fill defaults
            self.hashtags_var.set("#python, #terraform, #rstats")
            self.anchors_var.set("capitalweather.bsky.social")
            self.max_per_hashtag_var.set(100)
            self.max_per_anchor_var.set(200)
            self.fetch_posts_var.set(50)
            self.thresh_match_var.set(0.75)
            self.thresh_maybe_var.set(0.50)
            self.model_var.set("google/gemini-3-flash-preview")
            self.db_path_var.set("dctech.db")
            self.ttl_profile_var.set(24)
            self.ttl_posts_var.set(6)
            self.ttl_llm_var.set(168)

    def _apply_config(self):
        """Push GUI values back into the live settings object before a run."""
        from .config import settings

        # Hashtags / anchors
        settings.seed_hashtags = [
            h.strip() for h in self.hashtags_var.get().split(",") if h.strip()
        ]
        settings.anchor_handles = [
            a.strip() for a in self.anchors_var.get().split(",") if a.strip()
        ]

        # Limits
        settings.discovery_limits.max_candidates_per_hashtag = self.max_per_hashtag_var.get()
        settings.discovery_limits.max_accounts_per_anchor = self.max_per_anchor_var.get()
        settings.fetch_posts_limit = self.fetch_posts_var.get()

        # Scoring
        settings.scoring_thresholds.match_overall = self.thresh_match_var.get()
        settings.scoring_thresholds.maybe_overall = self.thresh_maybe_var.get()

        # LLM
        settings.openrouter_model = self.model_var.get()

        # TTLs
        settings.ttl_profile_hours = self.ttl_profile_var.get()
        settings.ttl_posts_hours = self.ttl_posts_var.get()
        settings.ttl_llm_hours = self.ttl_llm_var.get()

    # ---------- controls ----------

    def _build_controls(self, parent):
        ctl = ttk.Frame(parent, padding=4)
        ctl.pack(fill="x")

        # Options row
        self.force_var = tk.BooleanVar()
        ttk.Checkbutton(ctl, text="Force", variable=self.force_var).pack(side="left")

        ttk.Label(ctl, text="  Export:").pack(side="left")
        self.format_var = tk.StringVar(value="html")
        ttk.Combobox(ctl, textvariable=self.format_var, values=["html", "jsonl"],
                      state="readonly", width=6).pack(side="left", padx=4)

        ttk.Separator(ctl, orient="vertical").pack(side="left", fill="y", padx=8)

        # Buttons
        self.buttons = {}
        for label, cmd in [
            ("Discover", self._run_discover),
            ("Fetch", self._run_fetch),
            ("Evaluate", self._run_evaluate),
            ("Run All", self._run_all),
            ("Export", self._run_export),
        ]:
            b = ttk.Button(ctl, text=label, command=cmd)
            b.pack(side="left", padx=3)
            self.buttons[label] = b

    # ---------- log ----------

    def _build_log(self, parent):
        # Stats bar
        self.stats_var = tk.StringVar(value="Ready")
        ttk.Label(parent, textvariable=self.stats_var, relief="sunken",
                  anchor="w", padding=4).pack(fill="x", pady=(0, 4))

        log_frame = ttk.LabelFrame(parent, text="Output", padding=4)
        log_frame.pack(fill="both", expand=True)

        self.log = scrolledtext.ScrolledText(
            log_frame, wrap="word", state="disabled", font=("Consolas", 9)
        )
        self.log.pack(fill="both", expand=True)

        # Wire up Python logging -> the output widget
        self._setup_logging()

        self.root.after(100, self._load_stats)

    def _setup_logging(self):
        """Route the root logger (INFO+) into the output widget."""
        handler = _TkTextHandler(self.log)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s",
                              datefmt="%H:%M:%S")
        )
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(handler)

    # ---------- helpers ----------

    def _append_log(self, text: str):
        self.log.config(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.config(state="disabled")

    def _set_buttons_state(self, state: str):
        for b in self.buttons.values():
            b.config(state=state)

    def _load_stats(self):
        try:
            from .database import get_db, DbCandidate, DbLlmEval
            db = get_db()
            total = db.query(DbCandidate).count()
            evaluated = db.query(DbLlmEval).count()
            matched = db.query(DbLlmEval).filter(DbLlmEval.label == "match").count()
            maybe = db.query(DbLlmEval).filter(DbLlmEval.label == "maybe").count()
            db.close()
            self.stats_var.set(
                f"DB: {total} candidates | {evaluated} evaluated | "
                f"{matched} match | {maybe} maybe"
            )
        except Exception as e:
            self.stats_var.set(f"DB stats unavailable: {e}")

    def _run_in_thread(self, label: str, func):
        if self._running:
            return

        self._running = True
        self._set_buttons_state("disabled")
        self.stats_var.set(f"Running: {label}...")
        self._append_log(f"\n{'='*60}\n{label}\n{'='*60}\n")

        # Apply GUI config before every run
        try:
            self._apply_config()
        except Exception as e:
            self._append_log(f"Config error: {e}\n")

        def target():
            buf = StringIO()
            try:
                with redirect_stdout(buf), redirect_stderr(buf):
                    func()
                output = buf.getvalue()
                self.root.after(0, self._append_log, output)
                self.root.after(0, self.stats_var.set, f"{label} complete.")
            except Exception as exc:
                output = buf.getvalue()
                self.root.after(0, self._append_log, output + f"\nERROR: {exc}\n")
                self.root.after(0, self.stats_var.set, f"{label} failed: {exc}")
            finally:
                self.root.after(0, self._set_buttons_state, "normal")
                self.root.after(0, self._load_stats)
                self._running = False

        threading.Thread(target=target, daemon=True).start()

    def _get_pipeline(self):
        from .pipeline import Pipeline
        return Pipeline()

    # ---------- commands ----------

    def _run_discover(self):
        def work():
            self._get_pipeline().run_discovery()
        self._run_in_thread("Discover", work)

    def _run_fetch(self):
        force = self.force_var.get()
        def work():
            self._get_pipeline().run_fetch(force=force)
        self._run_in_thread("Fetch", work)

    def _run_evaluate(self):
        force = self.force_var.get()
        def work():
            self._get_pipeline().run_evaluation(force=force)
        self._run_in_thread("Evaluate", work)

    def _run_all(self):
        force = self.force_var.get()
        fmt = self.format_var.get()
        def work():
            p = self._get_pipeline()
            print("--- Step 1: Discover ---")
            p.run_discovery()
            print("\n--- Step 2: Fetch ---")
            p.run_fetch(force=force)
            print("\n--- Step 3: Evaluate ---")
            p.run_evaluation(force=force)
            print("\n--- Step 4: Export ---")
            p.export_results(format=fmt)
        self._run_in_thread("Run All", work)

    def _run_export(self):
        fmt = self.format_var.get()
        def work():
            self._get_pipeline().export_results(format=fmt)
        self._run_in_thread("Export", work)


def main():
    root = tk.Tk()
    PipelineGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
