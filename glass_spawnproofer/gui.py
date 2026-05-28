from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from glass_spawnproofer.logic.glass_mapping import MappingValidationError, default_mapping_payload, parse_user_mappings
from glass_spawnproofer.processor import process_schematic_file

PALETTE = {
    "bg": "#030303",
    "surface": "#0b0b0f",
    "surface_elevated": "#111118",
    "surface_soft": "#171722",
    "text": "#f5f5f7",
    "muted": "#a7a7b3",
    "soft": "#737381",
    "blue": "#0B00CF",
    "purple": "#300A6E",
    "red": "#FF2D2B",
    "deep_red": "#C10A28",
    "border": "#34343d",
}


def config_dir() -> Path:
    """Return the per-user config directory for custom mappings."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "Glass Spawnproofer"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Glass Spawnproofer"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "glass-spawnproofer"


class GlassSpawnprooferApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self._configure_dpi_scaling()
        self.title("Glass Spawnproofer")
        self.geometry("1060x820")
        self.minsize(840, 680)
        self.configure(bg=PALETTE["bg"])

        self.input_path: Path | None = None
        self.custom_mappings: dict[str, str] = {}
        self.config_file = config_dir() / "custom_mappings.json"
        self.default_payload = default_mapping_payload()
        self.colors = self.default_payload["colors"]
        self.color_display_to_id = {
            f"{item['label']} — {item['block_id']}": item["block_id"]
            for item in self.colors
        }

        self._configure_style()
        self._load_custom_mappings()
        self._build_ui()
        self._refresh_mapping_table()

    def _configure_dpi_scaling(self) -> None:
        """Ask Tk to render fonts and widgets at the real display DPI."""
        try:
            pixels_per_inch = float(self.winfo_fpixels("1i"))
            self.tk.call("tk", "scaling", pixels_per_inch / 72.0)
        except tk.TclError:
            pass

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("Treeview",
            background=PALETTE["surface"],
            fieldbackground=PALETTE["surface"],
            foreground=PALETTE["muted"],
            borderwidth=0,
            rowheight=30,
        )
        style.map("Treeview",
            background=[("selected", PALETTE["purple"])],
            foreground=[("selected", PALETTE["text"])],
        )
        style.configure("Treeview.Heading",
            background=PALETTE["surface_soft"],
            foreground=PALETTE["text"],
            borderwidth=0,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
        )
        style.configure("Horizontal.TProgressbar",
            background=PALETTE["red"],
            troughcolor=PALETTE["surface_soft"],
            bordercolor=PALETTE["surface_soft"],
            lightcolor=PALETTE["red"],
            darkcolor=PALETTE["deep_red"],
        )

    def _build_ui(self) -> None:
        tk.Frame(self, bg=PALETTE["red"], height=3).pack(fill="x", side="top")

        outer = tk.Frame(self, bg=PALETTE["bg"])
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, bg=PALETTE["bg"], highlightthickness=0)
        self.main_canvas = canvas
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        self.scroll_frame = tk.Frame(canvas, bg=PALETTE["bg"])
        self.scroll_frame.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas_window = canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(canvas_window, width=event.width))

        shell = tk.Frame(self.scroll_frame, bg=PALETTE["bg"])
        shell.pack(fill="both", expand=True, padx=34, pady=34)

        self._build_top_bar(shell)
        self._build_tool_card(shell)
        self._build_mapping_card(shell)
        self._build_footer(shell)
        self._bind_mousewheel_scrolling()

    def _bind_mousewheel_scrolling(self) -> None:
        """Make the mouse wheel scroll the main page on Windows, macOS, and Linux.

        Tkinter does not automatically connect mouse-wheel events to a Canvas.
        Without these bindings, users have to drag the scrollbar manually.
        """
        self.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.bind_all("<Button-4>", self._on_mousewheel, add="+")
        self.bind_all("<Button-5>", self._on_mousewheel, add="+")

    def _on_mousewheel(self, event: tk.Event) -> str:
        widget_under_pointer = self.winfo_containing(event.x_root, event.y_root)

        # If the cursor is over the custom-mapping table, scroll that table.
        # Everywhere else, scroll the main application page.
        target = self.mapping_table if widget_under_pointer is self.mapping_table else self.main_canvas

        if getattr(event, "num", None) == 4:
            units = -3
        elif getattr(event, "num", None) == 5:
            units = 3
        else:
            delta = getattr(event, "delta", 0)
            if delta == 0:
                units = 0
            elif sys.platform == "darwin":
                units = -1 if delta > 0 else 1
            else:
                units = -int(delta / 120)
                if units == 0:
                    units = -1 if delta > 0 else 1

        if units:
            target.yview_scroll(units, "units")
        return "break"

    def _build_top_bar(self, parent: tk.Widget) -> None:
        bar = tk.Frame(parent, bg=PALETTE["bg"])
        bar.pack(fill="x", pady=(0, 18))

        tk.Label(
            bar,
            text="Glass Spawnproofer",
            bg=PALETTE["bg"],
            fg=PALETTE["text"],
            font=("Segoe UI", 15, "bold"),
        ).pack(side="left")

        tk.Label(
            bar,
            text="Local desktop tool",
            bg=PALETTE["bg"],
            fg=PALETTE["soft"],
            font=("Segoe UI", 10),
        ).pack(side="right")

    def _card(self, parent: tk.Widget, accent: str | None = None) -> tk.Frame:
        wrap = tk.Frame(parent, bg=PALETTE["bg"])
        wrap.pack(fill="x", pady=(0, 22))
        card = tk.Frame(
            wrap,
            bg=PALETTE["surface_elevated"],
            highlightbackground=PALETTE["border"],
            highlightthickness=1,
            padx=32,
            pady=30,
        )
        card.pack(fill="x")
        if accent:
            tk.Frame(card, bg=accent, width=4).pack(fill="y", side="left", padx=(0, 22))
        return card

    def _build_tool_card(self, parent: tk.Widget) -> None:
        card = self._card(parent, PALETTE["red"])
        body = tk.Frame(card, bg=PALETTE["surface_elevated"])
        body.pack(fill="x", side="left", expand=True)

        tk.Label(
            body,
            text="Glass Spawnproofer",
            bg=PALETTE["surface_elevated"],
            fg=PALETTE["text"],
            font=("Segoe UI", 36, "bold"),
            anchor="w",
        ).pack(fill="x")

        tk.Label(
            body,
            text="A local spawnproofing marker for Minecraft schematics.",
            bg=PALETTE["surface_elevated"],
            fg=PALETTE["muted"],
            font=("Segoe UI", 13),
            anchor="w",
        ).pack(fill="x", pady=(10, 5))

        tk.Label(
            body,
            text=(
                "Open a .litematic file, detect potential hostile mob spawning spaces, "
                "place stained glass markers above them, and save a new .litematic."
            ),
            bg=PALETTE["surface_elevated"],
            fg=PALETTE["muted"],
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
            wraplength=820,
        ).pack(fill="x", pady=(0, 24))

        picker = tk.Frame(body, bg=PALETTE["surface"], highlightbackground=PALETTE["border"], highlightthickness=1, padx=18, pady=18)
        picker.pack(fill="x")

        self.file_label = tk.Label(
            picker,
            text="No schematic selected",
            bg=PALETTE["surface"],
            fg=PALETTE["muted"],
            font=("Segoe UI", 11),
            anchor="w",
        )
        self.file_label.pack(side="left", fill="x", expand=True)

        self.choose_button = self._button(picker, "Choose .litematic", self._choose_file, bg=PALETTE["surface_soft"])
        self.choose_button.pack(side="right", padx=(12, 0))

        actions = tk.Frame(body, bg=PALETTE["surface_elevated"])
        actions.pack(fill="x", pady=(18, 0))

        self.process_button = self._button(actions, "Process and save marked schematic", self._start_processing, bg=PALETTE["red"])
        self.process_button.pack(side="left")

        self.progress = ttk.Progressbar(actions, mode="indeterminate", style="Horizontal.TProgressbar", length=180)
        self.progress.pack(side="left", padx=(16, 0))
        self.progress.pack_forget()

        self.status_label = tk.Label(
            body,
            text="Ready.",
            bg=PALETTE["surface_elevated"],
            fg=PALETTE["soft"],
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        )
        self.status_label.pack(fill="x", pady=(18, 0))

    def _build_mapping_card(self, parent: tk.Widget) -> None:
        card = self._card(parent, PALETTE["blue"])
        body = tk.Frame(card, bg=PALETTE["surface_elevated"])
        body.pack(fill="both", side="left", expand=True)

        heading_row = tk.Frame(body, bg=PALETTE["surface_elevated"])
        heading_row.pack(fill="x")

        tk.Label(
            heading_row,
            text="Custom block → glass colors",
            bg=PALETTE["surface_elevated"],
            fg=PALETTE["text"],
            font=("Segoe UI", 22, "bold"),
            anchor="w",
        ).pack(side="left")

        self.reset_button = self._button(heading_row, "Clear custom mappings", self._clear_mappings, bg=PALETTE["surface_soft"])
        self.reset_button.pack(side="right")

        tk.Label(
            body,
            text="Add exact block preferences here. These override the built-in defaults when you process a schematic.",
            bg=PALETTE["surface_elevated"],
            fg=PALETTE["muted"],
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
            wraplength=820,
        ).pack(fill="x", pady=(10, 20))

        form = tk.Frame(body, bg=PALETTE["surface_elevated"])
        form.pack(fill="x")

        block_wrap = tk.Frame(form, bg=PALETTE["surface_elevated"])
        block_wrap.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self._field_label(block_wrap, "Block ID").pack(fill="x")
        self.block_entry = tk.Entry(
            block_wrap,
            bg=PALETTE["surface"],
            fg=PALETTE["text"],
            insertbackground=PALETTE["text"],
            relief="flat",
            highlightbackground=PALETTE["border"],
            highlightcolor=PALETTE["red"],
            highlightthickness=1,
            font=("Segoe UI", 11),
        )
        self.block_entry.pack(fill="x", ipady=10)
        self.block_entry.insert(0, "minecraft:gold_block")

        color_wrap = tk.Frame(form, bg=PALETTE["surface_elevated"])
        color_wrap.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self._field_label(color_wrap, "Glass color").pack(fill="x")
        self.color_combo = ttk.Combobox(
            color_wrap,
            values=list(self.color_display_to_id.keys()),
            state="readonly",
            font=("Segoe UI", 10),
        )
        self.color_combo.pack(fill="x", ipady=7)
        self.color_combo.current(0)

        add_wrap = tk.Frame(form, bg=PALETTE["surface_elevated"])
        add_wrap.pack(side="left", anchor="s")
        self.add_button = self._button(add_wrap, "Add mapping", self._add_mapping, bg=PALETTE["purple"])
        self.add_button.pack()

        table_wrap = tk.Frame(body, bg=PALETTE["surface"], highlightbackground=PALETTE["border"], highlightthickness=1)
        table_wrap.pack(fill="both", expand=True, pady=(18, 0))

        self.mapping_table = ttk.Treeview(
            table_wrap,
            columns=("block", "glass"),
            show="headings",
            height=8,
        )
        self.mapping_table.heading("block", text="Block")
        self.mapping_table.heading("glass", text="Glass")
        self.mapping_table.column("block", width=380, anchor="w")
        self.mapping_table.column("glass", width=330, anchor="w")
        self.mapping_table.pack(side="left", fill="both", expand=True)

        table_scroll = ttk.Scrollbar(table_wrap, orient="vertical", command=self.mapping_table.yview)
        table_scroll.pack(side="right", fill="y")
        self.mapping_table.configure(yscrollcommand=table_scroll.set)

        below = tk.Frame(body, bg=PALETTE["surface_elevated"])
        below.pack(fill="x", pady=(12, 0))
        self.remove_button = self._button(below, "Remove selected", self._remove_selected_mapping, bg=PALETTE["surface_soft"])
        self.remove_button.pack(side="left")

    def _build_footer(self, parent: tk.Widget) -> None:
        footer = tk.Frame(parent, bg=PALETTE["bg"])
        footer.pack(fill="x", pady=(6, 0))
        tk.Label(
            footer,
            text=(
                "Glass Spawnproofer is an independent tool and is not an official Minecraft product. "
                "It is not approved by or associated with Mojang or Microsoft."
            ),
            bg=PALETTE["bg"],
            fg=PALETTE["soft"],
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=960,
        ).pack(fill="x")

    def _button(self, parent: tk.Widget, text: str, command, bg: str) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            activebackground=PALETTE["deep_red"],
            fg=PALETTE["text"],
            activeforeground=PALETTE["text"],
            relief="flat",
            borderwidth=0,
            padx=16,
            pady=10,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
        )

    def _field_label(self, parent: tk.Widget, text: str) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            bg=PALETTE["surface_elevated"],
            fg=PALETTE["muted"],
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        )

    def _load_custom_mappings(self) -> None:
        if not self.config_file.exists():
            self.custom_mappings = {}
            return
        try:
            raw = self.config_file.read_text(encoding="utf-8")
            self.custom_mappings = parse_user_mappings(raw)
        except Exception:
            self.custom_mappings = {}

    def _save_custom_mappings(self) -> None:
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text(json.dumps(self.custom_mappings, indent=2, sort_keys=True), encoding="utf-8")

    def _refresh_mapping_table(self) -> None:
        for item in self.mapping_table.get_children():
            self.mapping_table.delete(item)
        if not self.custom_mappings:
            self.mapping_table.insert("", "end", values=("No custom mappings yet", ""), tags=("empty",))
            return
        for block, glass in sorted(self.custom_mappings.items()):
            self.mapping_table.insert("", "end", values=(block, glass))

    def _choose_file(self) -> None:
        filename = filedialog.askopenfilename(
            title="Choose schematic",
            filetypes=[
                ("Litematica schematics", "*.litematic"),
                ("Sponge schematics", "*.schem"),
                ("All files", "*.*"),
            ],
        )
        if not filename:
            return
        self.input_path = Path(filename)
        self.file_label.configure(text=str(self.input_path))
        self._set_status("Schematic selected.")

    def _suggest_output_path(self) -> Path:
        assert self.input_path is not None
        return self.input_path.with_name(f"{self.input_path.stem}_spawn_marked.litematic")

    def _start_processing(self) -> None:
        if self.input_path is None:
            messagebox.showwarning("Choose a file", "Choose a .litematic file first.")
            return

        output_name = filedialog.asksaveasfilename(
            title="Save marked schematic",
            initialfile=self._suggest_output_path().name,
            initialdir=str(self.input_path.parent),
            defaultextension=".litematic",
            filetypes=[("Litematica schematic", "*.litematic")],
        )
        if not output_name:
            return

        output_path = Path(output_name)
        mappings = dict(self.custom_mappings)
        self._set_busy(True)
        self._set_status("Processing schematic locally...")

        thread = threading.Thread(
            target=self._process_worker,
            args=(self.input_path, output_path, mappings),
            daemon=True,
        )
        thread.start()

    def _process_worker(self, input_path: Path, output_path: Path, mappings: dict[str, str]) -> None:
        try:
            result = process_schematic_file(input_path, output_path, mappings)
        except Exception as exc:
            self.after(0, lambda: self._process_failed(exc))
            return
        self.after(0, lambda: self._process_complete(result, output_path))

    def _process_complete(self, result, output_path: Path) -> None:
        self._set_busy(False)
        self._set_status(
            f"Done. Found {result.candidates} potential spawn spaces and placed {result.placed} glass markers."
        )
        messagebox.showinfo(
            "Schematic saved",
            (
                f"Saved marked schematic:\n{output_path}\n\n"
                f"Regions: {result.regions}\n"
                f"Potential spawn spaces: {result.candidates}\n"
                f"Glass markers placed: {result.placed}"
            ),
        )

    def _process_failed(self, exc: Exception) -> None:
        self._set_busy(False)
        messagebox.showerror("Could not process schematic", str(exc))
        self._set_status(f"Error: {exc}", error=True)

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.process_button.configure(state=state)
        self.choose_button.configure(state=state)
        self.add_button.configure(state=state)
        self.remove_button.configure(state=state)
        self.reset_button.configure(state=state)
        if busy:
            self.progress.pack(side="left", padx=(16, 0))
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.pack_forget()

    def _set_status(self, text: str, error: bool = False) -> None:
        self.status_label.configure(text=text, fg=PALETTE["red"] if error else PALETTE["soft"])

    def _add_mapping(self) -> None:
        block = self.block_entry.get().strip()
        glass_display = self.color_combo.get().strip()
        glass = self.color_display_to_id.get(glass_display, glass_display)
        try:
            parsed = parse_user_mappings(json.dumps({block: glass}))
        except MappingValidationError as exc:
            messagebox.showerror("Invalid mapping", str(exc))
            return

        self.custom_mappings.update(parsed)
        self._save_custom_mappings()
        self._refresh_mapping_table()
        normalized_block = next(iter(parsed.keys()))
        self._set_status(f"Added custom mapping for {normalized_block}.")

    def _remove_selected_mapping(self) -> None:
        selected = self.mapping_table.selection()
        if not selected:
            return
        removed = False
        for item in selected:
            values = self.mapping_table.item(item, "values")
            if not values:
                continue
            block = values[0]
            if block in self.custom_mappings:
                del self.custom_mappings[block]
                removed = True
        if removed:
            self._save_custom_mappings()
            self._refresh_mapping_table()
            self._set_status("Removed selected custom mapping.")

    def _clear_mappings(self) -> None:
        if not self.custom_mappings:
            return
        if not messagebox.askyesno("Clear custom mappings", "Remove all custom block-to-glass mappings?"):
            return
        self.custom_mappings.clear()
        self._save_custom_mappings()
        self._refresh_mapping_table()
        self._set_status("Custom mappings cleared.")


def main() -> int:
    app = GlassSpawnprooferApp()
    app.mainloop()
    return 0
