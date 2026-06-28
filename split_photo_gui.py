import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import os

class PhotoSplitterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Photo Splitter 3/2 → 3/4")
        self.root.geometry("600x550")
        
        self.input_path = None
        self.preview_image = None
        
        # Chemins par défaut
        self.default_input_dir = "/mnt/c/Documents and Settings/riwal/Photos/2026/exported_new"
        self.default_output_dir = "/mnt/c/Documents and Settings/riwal/Photos/2026/exported_new/insta"
        
        # Créer le dossier de sortie s'il n'existe pas
        os.makedirs(self.default_output_dir, exist_ok=True)
        
        # Frame principal
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Titre
        title = ttk.Label(main_frame, text="Découpage photo 3/2 paysage → 2x 3/4 portrait", 
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
        
        # Info sortie
        output_info = ttk.Label(main_frame, text=f"📁 Sortie: .../insta/", 
                               foreground="gray", font=("Arial", 9))
        output_info.grid(row=5, column=0, columnspan=2, pady=2)
        
        # Bouton découper
        self.btn_split = ttk.Button(main_frame, text="✂️ Découper la photo", 
                                    command=self.split_photo, state="disabled")
        self.btn_split.grid(row=6, column=0, columnspan=2, pady=15)
        
        # Barre de progression
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
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
            self.btn_split.config(state="normal")
    
    def load_preview(self):
        try:
            img = Image.open(self.input_path)
            width, height = img.size
            
            # Afficher les dimensions
            ratio = width / height
            
            # Pour du 3/4 portrait, on veut: hauteur = largeur * 4/3
            # Donc la largeur de chaque photo sera: largeur_cible
            # Et la hauteur: largeur_cible * 4/3
            
            # On va prendre la moitié de la largeur pour chaque photo
            target_width = width // 2
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
            
            self.info_label.config(text=info_text)
            
            # Créer une miniature pour l'aperçu
            img.thumbnail((250, 250))
            self.preview_image = ImageTk.PhotoImage(img)
            self.preview_label.config(image=self.preview_image, text="")
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de charger l'image:\n{str(e)}")
    
    def split_photo(self):
        if not self.input_path:
            return
        
        try:
            self.progress.start()
            self.btn_split.config(state="disabled")
            
            # Ouvrir l'image
            img = Image.open(self.input_path)
            width, height = img.size
            
            # Calculer les dimensions pour chaque photo 3/4 portrait
            target_width = width // 2
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
            
            # Découper partie gauche
            photo_left = img.crop((0, crop_top, target_width, crop_bottom))
            
            # Découper partie droite
            photo_right = img.crop((target_width, crop_top, width, crop_bottom))
            
            # Noms de fichiers - SAUVEGARDER DANS LE DOSSIER INSTA
            base_name = os.path.splitext(os.path.basename(self.input_path))[0]
            ext = os.path.splitext(self.input_path)[1]
            
            output_left = os.path.join(self.default_output_dir, f"{base_name}_left{ext}")
            output_right = os.path.join(self.default_output_dir, f"{base_name}_right{ext}")
            
            # Sauvegarder
            photo_left.save(output_left, quality=95)
            photo_right.save(output_right, quality=95)
            
            self.progress.stop()
            self.btn_split.config(state="normal")
            
            messagebox.showinfo("Succès", 
                f"Photos créées avec succès dans /insta/ !\n\n"
                f"📸 {os.path.basename(output_left)}\n"
                f"📸 {os.path.basename(output_right)}")
            
        except Exception as e:
            self.progress.stop()
            self.btn_split.config(state="normal")
            messagebox.showerror("Erreur", f"Erreur lors du découpage:\n{str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = PhotoSplitterApp(root)
    root.mainloop()