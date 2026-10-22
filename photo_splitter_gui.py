#!/usr/bin/env python3
import os
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageOps, ImageTk

from utils import (
    CONFIG_PATH,
    DEFAULT_FRAME_RATIO,
    DEFAULT_LANDSCAPE_FILL_MODE,
    gather_input_files,
    load_config,
    process_image,
    save_config,
)
from version import __version__


class PhotoSplitterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Photo Splitter LR → Instagram v{__version__}")
        self.root.geometry("1100x750")
        self.root.minsize(1000, 700)

        self.config = load_config(CONFIG_PATH)
        self.selected_paths = []
        self.preview_image = None

        self.source_dir = tk.StringVar(value=self.config.get("last_source_dir", ""))
        self.dest_dir = tk.StringVar(value=self.config.get("last_dest_dir", "output"))
        self.frame_ratio = tk.DoubleVar(value=self.config.get("frame_ratio", DEFAULT_FRAME_RATIO))
        self.landscape_fill_mode = tk.StringVar(value=self.config.get("landscape_fill_mode", DEFAULT_LANDSCAPE_FILL_MODE))
        self.signature_path = tk.StringVar(value=self.config.get("signature_path", ""))
        self.status_text = tk.StringVar(value="Prêt à traiter.")
        self.selected_file_info = tk.StringVar(value="Sélectionnez une image pour l'aperçu.")

        self.build_ui()

    def build_ui(self):
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(container, text="Photo Splitter LR → Insta", font=("Segoe UI", 18, "bold"))
        title.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 12))

        group_paths = ttk.LabelFrame(container, text="Fichiers / Dossiers source", padding=10)
        group_paths.grid(row=1, column=0, columnspan=3, sticky=tk.NSEW, pady=8)

        btn_frame = ttk.Frame(group_paths)
        btn_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(btn_frame, text="Ajouter fichiers", command=self.add_files).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="Ajouter dossier", command=self.add_folder).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="Effacer la sélection", command=self.clear_selection).pack(side=tk.LEFT)

        list_frame = ttk.Frame(group_paths)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE, height=10)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox.bind("<<ListboxSelect>>", self.on_list_select)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scrollbar.set)

        frame_options = ttk.LabelFrame(container, text="Options", padding=10)
        frame_options.grid(row=2, column=0, columnspan=3, sticky=tk.NSEW, pady=8)

        ttk.Label(frame_options, text="Dossier de destination:").grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 4))
        dest_entry = ttk.Entry(frame_options, textvariable=self.dest_dir, width=60, state="readonly")
        dest_entry.grid(row=1, column=0, sticky=tk.EW, padx=(0, 8))
        ttk.Button(frame_options, text="Choisir le dossier", command=self.choose_dest).grid(row=1, column=1, padx=(0, 4))
        ttk.Button(frame_options, text="Ouvrir", command=self.open_dest_folder).grid(row=1, column=2)
        
        ttk.Label(frame_options, text="Épaisseur du cadre (ratio):").grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(12, 4))
        
        ratio_frame = ttk.Frame(frame_options)
        ratio_frame.grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=(0, 4))
        ttk.Spinbox(
            ratio_frame,
            from_=0.01,
            to=0.2,
            increment=0.01,
            textvariable=self.frame_ratio,
            width=8,
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(ratio_frame, text="(0.04 = 4 % de la plus petite dimension)").pack(side=tk.LEFT)

        ttk.Label(frame_options, text="Fond du portrait 3/4 (paysages et portraits 2/3):").grid(
            row=4, column=0, columnspan=3, sticky=tk.W, pady=(12, 4)
        )
        fill_mode_frame = ttk.Frame(frame_options)
        fill_mode_frame.grid(row=5, column=0, columnspan=3, sticky=tk.W, pady=(0, 4))
        ttk.Radiobutton(
            fill_mode_frame,
            text="Fond noir",
            value="black",
            variable=self.landscape_fill_mode,
        ).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Radiobutton(
            fill_mode_frame,
            text="Fond flouté (image étendue)",
            value="blur",
            variable=self.landscape_fill_mode,
        ).pack(side=tk.LEFT)

        ttk.Label(frame_options, text="Signature (optionnel):").grid(row=6, column=0, columnspan=3, sticky=tk.W, pady=(12, 4))

        sig_frame = ttk.Frame(frame_options)
        sig_frame.grid(row=7, column=0, columnspan=3, sticky=tk.EW)
        sig_entry = ttk.Entry(sig_frame, textvariable=self.signature_path, width=60, state="readonly")
        sig_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Button(sig_frame, text="Choisir signature", command=self.choose_signature).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(sig_frame, text="Effacer", command=self.clear_signature).pack(side=tk.LEFT)

        ttk.Button(frame_options, text="Enregistrer les préférences", command=self.save_preferences).grid(
            row=8, column=0, columnspan=3, pady=(14, 0), sticky=tk.W
        )

        frame_options.columnconfigure(0, weight=1)

        preview_frame = ttk.LabelFrame(container, text="Aperçu et informations", padding=10)
        preview_frame.grid(row=1, column=3, rowspan=2, sticky=tk.NSEW, padx=(12, 0), pady=8)

        self.canvas = tk.Canvas(preview_frame, width=400, height=360, bg="#f0f0f0", highlightthickness=1)
        self.canvas.pack(fill=tk.BOTH, expand=False)

        ttk.Label(preview_frame, textvariable=self.selected_file_info, wraplength=380, justify=tk.LEFT).pack(fill=tk.X, pady=(8, 0))

        control_frame = ttk.Frame(container)
        control_frame.grid(row=3, column=0, columnspan=4, sticky=tk.EW, pady=12)

        self.process_button = ttk.Button(control_frame, text="Lancer le traitement", command=self.start_processing)
        self.process_button.pack(side=tk.RIGHT)
        ttk.Button(control_frame, text="À propos", command=self.show_about).pack(side=tk.LEFT)

        self.status_bar = ttk.Label(self.root, textvariable=self.status_text, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        container.columnconfigure(0, weight=1)
        container.columnconfigure(3, weight=0)
        container.rowconfigure(1, weight=1)
        container.rowconfigure(2, weight=0)

    def show_about(self):
        messagebox.showinfo(
            "À propos",
            f"Photo Splitter LR → Instagram\nVersion {__version__}\n\nhttps://github.com/kerherve/imageSplitter",
        )

    def add_files(self):
        initial_dir = self.source_dir.get() or os.getcwd()
        files = filedialog.askopenfilenames(
            title="Sélectionner des fichiers image",
            initialdir=initial_dir,
            filetypes=[("Images", "*.jpg *.jpeg *.png *.tiff *.bmp"), ("Tous", "*.*")],
        )
        if files:
            self.selected_paths.extend(files)
            self.source_dir.set(str(Path(files[0]).parent))
            self.refresh_list()

    def add_folder(self):
        folder = filedialog.askdirectory(title="Sélectionner un dossier source", initialdir=self.source_dir.get() or os.getcwd())
        if folder:
            self.selected_paths.append(folder)
            self.source_dir.set(folder)
            self.refresh_list()

    def clear_selection(self):
        self.selected_paths = []
        self.listbox.delete(0, tk.END)
        self.preview_image = None
        self.canvas.delete("all")
        self.selected_file_info.set("Sélectionnez une image pour l'aperçu.")

    def choose_dest(self):
        folder = filedialog.askdirectory(title="Choisir le dossier de destination", initialdir=self.dest_dir.get() or os.getcwd())
        if folder:
            self.dest_dir.set(folder)

    def open_dest_folder(self):
        folder = self.dest_dir.get()
        if not folder:
            messagebox.showwarning("Dossier manquant", "Choisissez d’abord un dossier de destination.")
            return
        folder_path = Path(folder)
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(folder_path)
            else:
                os.system(f"xdg-open '{folder_path}'")
        except Exception as exc:
            messagebox.showerror("Erreur", f"Impossible d’ouvrir le dossier : {exc}")

    def choose_signature(self):
        initial_dir = os.path.expanduser("~")
        sig_file = filedialog.askopenfilename(
            title="Sélectionner une signature",
            initialdir=initial_dir,
            filetypes=[("Images PNG", "*.png"), ("Images", "*.jpg *.jpeg *.bmp"), ("Tous", "*.*")],
        )
        if sig_file:
            self.signature_path.set(sig_file)

    def clear_signature(self):
        self.signature_path.set("")

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        unique_paths = []
        for path in self.selected_paths:
            if path not in unique_paths:
                unique_paths.append(path)
        self.selected_paths = unique_paths
        for path in unique_paths:
            self.listbox.insert(tk.END, path)

    def on_list_select(self, event):
        if not self.listbox.curselection():
            return
        index = self.listbox.curselection()[0]
        path = self.selected_paths[index]
        path_obj = Path(path)
        if path_obj.is_file():
            self.show_preview(path_obj)
        else:
            self.canvas.delete("all")
            self.selected_file_info.set(f"Dossier : {path}\nContient les images et sera traité en lot.")

    def show_preview(self, path: Path):
        try:
            img = Image.open(path)
            img = ImageOps.exif_transpose(img)
            img.thumbnail((400, 360))
            self.preview_image = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.create_image(200, 180, image=self.preview_image)
            width, height = img.size
            ratio = width / height if height else 0
            self.selected_file_info.set(f"{path.name}\n{width}×{height} px, ratio {ratio:.3f}")
        except Exception as exc:
            self.selected_file_info.set(f"Erreur aperçu : {exc}")

    def save_preferences(self):
        self.config["last_source_dir"] = self.source_dir.get()
        self.config["last_dest_dir"] = self.dest_dir.get()
        self.config["frame_ratio"] = self.frame_ratio.get()
        self.config["landscape_fill_mode"] = self.landscape_fill_mode.get()
        self.config["signature_path"] = self.signature_path.get()
        save_config(CONFIG_PATH, self.config)
        self.status_text.set("Préférences sauvegardées.")

    def start_processing(self):
        if not self.selected_paths:
            messagebox.showwarning("Aucun fichier", "Ajoutez au moins un fichier ou un dossier source.")
            return
        if not self.dest_dir.get():
            messagebox.showwarning("Destination manquante", "Choisissez un dossier de destination.")
            return

        self.config["last_source_dir"] = self.source_dir.get()
        self.config["last_dest_dir"] = self.dest_dir.get()
        self.config["frame_ratio"] = self.frame_ratio.get()
        self.config["landscape_fill_mode"] = self.landscape_fill_mode.get()
        self.config["signature_path"] = self.signature_path.get()
        save_config(CONFIG_PATH, self.config)

        self.process_button.config(state=tk.DISABLED)
        self.status_text.set("Traitement en cours...")
        self.root.update_idletasks()

        thread = threading.Thread(target=self.process_batch)
        thread.start()

    def process_batch(self):
        try:
            files = gather_input_files(self.selected_paths)
            if not files:
                self.status_text.set("Aucun fichier image trouvé dans la sélection.")
                self.process_button.config(state=tk.NORMAL)
                return

            output_dir = Path(self.dest_dir.get())
            output_dir.mkdir(parents=True, exist_ok=True)

            processed = 0
            for path in files:
                try:
                    process_image(path, output_dir, self.config)
                    processed += 1
                    self.status_text.set(f"{processed}/{len(files)} traité(s) : {path.name}")
                    self.root.update_idletasks()
                except Exception as exc:
                    print(f"Erreur sur {path}: {exc}")

            self.status_text.set(f"Terminé : {processed}/{len(files)} fichier(s) traités.")
            messagebox.showinfo("Terminé", f"Traitement terminé : {processed}/{len(files)} fichier(s) traités.")
        finally:
            self.process_button.config(state=tk.NORMAL)


if __name__ == "__main__":
    root = tk.Tk()
    app = PhotoSplitterGUI(root)
    root.mainloop()
