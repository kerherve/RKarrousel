import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import os

class PhotoSplitterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Photo Splitter")
        self.root.geometry("600x600")
        
        self.input_path = None
        self.preview_image = None
        self.split_mode = None  # 2 ou 3 parties
        
        # Chemins par défaut
        self.default_input_dir = "/mnt/c/Documents and Settings/riwal/Photos/2026/exported_new"
        self.default_output_dir = "/mnt/c/Documents and Settings/riwal/Photos/2026/exported_new/insta"
        
        # Créer le dossier de sortie s'il n'existe pas
        os.makedirs(self.default_output_dir, exist_ok=True)
        
        # Frame principal
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Titre
        title = ttk.Label(main_frame, text="Découpage photo paysage → 3/4 portrait", 
                         font=("Arial", 14, "bold"))
        title.grid(row=0, column=0, columnspan=2, pady=10)
        
        # Sélection du fichier
        self.file_label = ttk.Label(main_frame, text="Aucun fichier sélectionné", 
                                   foreground="gray")
        self.file_label.grid(row=1, column=0, columnspan=2, pady=5)
        
        btn_select = ttk.Button(main_frame, text="📁 Choisir une photo", 
                               command=self.select_file)
        btn_select.grid(row=2, column=0, columnspan=2, pady=10)
        
        # Preview frame
        preview_frame = ttk.LabelFrame(main_frame, text="Aperçu", padding="5")
        preview_frame.grid(row=3, column=0, columnspan=2, pady=10, sticky=(tk.W, tk.E))
        
        self.preview_label = ttk.Label(preview_frame, text="Sélectionnez une photo pour voir l'aperçu")
        self.preview_label.pack()
        
        # Info dimensions
        self.info_label = ttk.Label(main_frame, text="", foreground="blue", wraplength=550)
        self.info_label.grid(row=4, column=0, columnspan=2, pady=5)
        
        # Info mode de découpe
        self.mode_label = ttk.Label(main_frame, text="", foreground="green", 
                                   font=("Arial", 10, "bold"))
        self.mode_label.grid(row=5, column=0, columnspan=2, pady=2)
        
        # Info sortie
        output_info = ttk.Label(main_frame, text=f"📁 Sortie: .../insta/", 
                               foreground="gray", font=("Arial", 9))
        output_info.grid(row=6, column=0, columnspan=2, pady=2)
        
        # Bouton découper
        self.btn_split = ttk.Button(main_frame, text="✂️ Découper la photo", 
                                    command=self.split_photo, state="disabled")
        self.btn_split.grid(row=7, column=0, columnspan=2, pady=15)
        
        # Barre de progression
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=8, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
    def select_file(self):
        # Ouvrir dans le dossier par défaut
        initial_dir = self.default_input_dir if os.path.exists(self.default_input_dir) else "~"
        
        filename = filedialog.askopenfilename(
            title="Sélectionner une photo",
            initialdir=initial_dir,
            filetypes=[
                ("Images", "*.jpg *.jpeg *.png *.tiff *.bmp"),
                ("Tous les fichiers", "*.*")
            ]
        )
        
        if filename:
            self.input_path = filename
            self.file_label.config(text=os.path.basename(filename), foreground="black")
            self.load_preview()
    
    def load_preview(self):
        try:
            img = Image.open(self.input_path)
            width, height = img.size
            
            # Afficher les dimensions
            ratio = width / height
            
            # Déterminer le mode de découpe basé sur le ratio
            # 3/2 = 1.5 → découpe en 2 parties
            # 9/4 = 2.25 → découpe en 3 parties
            
            ratio_2_parts = 3 / 2  # 1.5
            ratio_3_parts = 9 / 4  # 2.25
            
            # Tolérance de 5%
            if abs(ratio - ratio_2_parts) / ratio_2_parts < 0.05:
                self.split_mode = 2
                mode_text = "Mode: 3/2 → 2 photos 3/4"
                num_parts = 2
            elif abs(ratio - ratio_3_parts) / ratio_3_parts < 0.05:
                self.split_mode = 3
                mode_text = "Mode: 9/4 → 3 photos 3/4"
                num_parts = 3
            else:
                self.split_mode = None
                self.mode_label.config(text=f"⚠️ Ratio non supporté: {ratio:.3f}", foreground="red")
                self.info_label.config(text=f"Image: {width}x{height}\nRatios supportés: 3/2 (1.5) ou 9/4 (2.25)", 
                                      foreground="red")
                self.btn_split.config(state="disabled")
                
                # Miniature quand même
                img.thumbnail((250, 250))
                self.preview_image = ImageTk.PhotoImage(img)
                self.preview_label.config(image=self.preview_image, text="")
                return
            
            self.mode_label.config(text=mode_text, foreground="green")
            
            # Calculer les dimensions pour chaque photo 3/4 portrait
            target_width = width // num_parts
            target_height = int(target_width * 4 / 3)
            
            info_text = f"Image: {width}x{height} (ratio {ratio:.3f})\n"
            info_text += f"Chaque photo: {target_width}x{target_height} (ratio 3/4 portrait)"
            
            # Vérifier si la hauteur est suffisante
            if target_height > height:
                info_text += f"\n⚠️ Image trop petite en hauteur (besoin de {target_height}px)"
                self.info_label.config(foreground="red")
                self.btn_split.config(state="disabled")
            else:
                self.info_label.config(foreground="blue")
                self.btn_split.config(state="normal")
            
            self.info_label.config(text=info_text)
            
            # Créer une miniature pour l'aperçu
            img.thumbnail((250, 250))
            self.preview_image = ImageTk.PhotoImage(img)
            self.preview_label.config(image=self.preview_image, text="")
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de charger l'image:\n{str(e)}")
    
    def split_photo(self):
        if not self.input_path or not self.split_mode:
            return
        
        try:
            self.progress.start()
            self.btn_split.config(state="disabled")
            
            # Ouvrir l'image
            img = Image.open(self.input_path)
            width, height = img.size
            
            num_parts = self.split_mode
            
            # Calculer les dimensions pour chaque photo 3/4 portrait
            target_width = width // num_parts
            target_height = int(target_width * 4 / 3)
            
            # Vérifier la faisabilité
            if target_height > height:
                messagebox.showerror("Erreur", 
                    f"La hauteur de l'image ({height}px) est trop petite.\n"
                    f"Il faut au minimum {target_height}px de hauteur.")
                self.progress.stop()
                self.btn_split.config(state="normal")
                return
            
            # Calculer le centrage vertical
            vertical_margin = (height - target_height) // 2
            crop_top = vertical_margin
            crop_bottom = crop_top + target_height
            
            # Découper les photos
            photos = []
            suffixes = ["left", "center", "right"] if num_parts == 3 else ["left", "right"]
            
            for i in range(num_parts):
                left_x = i * target_width
                right_x = (i + 1) * target_width
                photo = img.crop((left_x, crop_top, right_x, crop_bottom))
                photos.append((photo, suffixes[i]))
            
            # Noms de fichiers - SAUVEGARDER DANS LE DOSSIER INSTA
            base_name = os.path.splitext(os.path.basename(self.input_path))[0]
            ext = os.path.splitext(self.input_path)[1]
            
            output_files = []
            for photo, suffix in photos:
                output_path = os.path.join(self.default_output_dir, f"{base_name}_{suffix}{ext}")
                photo.save(output_path, quality=95)
                output_files.append(os.path.basename(output_path))
            
            self.progress.stop()
            self.btn_split.config(state="normal")
            
            files_text = "\n".join([f"📸 {f}" for f in output_files])
            messagebox.showinfo("Succès", 
                f"Photos créées avec succès dans /insta/ !\n\n{files_text}")
            
        except Exception as e:
            self.progress.stop()
            self.btn_split.config(state="normal")
            messagebox.showerror("Erreur", f"Erreur lors du découpage:\n{str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = PhotoSplitterApp(root)
    root.mainloop()