from PIL import Image
import sys
import os

def split_photo_2_3_to_3_4(input_path, output_dir=None):
    """
    Découpe une photo au format 2/3 (ex: 4000x6000) en deux photos 3/4 portrait (ex: 3000x4000)
    
    Args:
        input_path: Chemin vers la photo source
        output_dir: Dossier de sortie (optionnel, par défaut même dossier que l'input)
    """
    # Ouvrir l'image
    img = Image.open(input_path)
    width, height = img.size
    
    print(f"Image source: {width}x{height}")
    
    # Vérifier le ratio (tolérance de 1%)
    ratio = width / height
    expected_ratio = 2 / 3
    if abs(ratio - expected_ratio) > 0.01:
        print(f"⚠️  Attention: le ratio de l'image ({ratio:.3f}) ne correspond pas exactement à 2/3 ({expected_ratio:.3f})")
        response = input("Continuer quand même ? (o/n): ")
        if response.lower() != 'o':
            return
    
    # Calculer les dimensions pour du 3/4 portrait
    # On veut garder la largeur et calculer la hauteur correspondante
    target_width = width
    target_height = int(width * 4 / 3)
    
    print(f"Dimensions cibles pour chaque photo: {target_width}x{target_height}")
    
    # Vérifier qu'on peut faire deux découpes
    if target_height * 2 > height:
        print(f"❌ Erreur: la hauteur de l'image ({height}) est trop petite pour découper deux photos {target_width}x{target_height}")
        print(f"   Il faudrait au minimum {target_height * 2} pixels de hauteur")
        return
    
    # Calculer les positions de découpe
    # On centre les deux découpes dans l'image source
    total_crop_height = target_height * 2
    vertical_margin = (height - total_crop_height) // 2
    
    # Première photo (haut)
    crop1_top = vertical_margin
    crop1_bottom = crop1_top + target_height
    
    # Deuxième photo (bas)
    crop2_top = crop1_bottom
    crop2_bottom = crop2_top + target_height
    
    # Découper les deux photos
    photo1 = img.crop((0, crop1_top, width, crop1_bottom))
    photo2 = img.crop((0, crop2_top, width, crop2_bottom))
    
    # Préparer les noms de fichiers de sortie
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    ext = os.path.splitext(input_path)[1]
    
    if output_dir is None:
        output_dir = os.path.dirname(input_path)
    
    os.makedirs(output_dir, exist_ok=True)
    
    output1 = os.path.join(output_dir, f"{base_name}_part1{ext}")
    output2 = os.path.join(output_dir, f"{base_name}_part2{ext}")
    
    # Sauvegarder
    photo1.save(output1, quality=95)
    photo2.save(output2, quality=95)
    
    print(f"✅ Photos créées:")
    print(f"   - {output1}")
    print(f"   - {output2}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python split_photo.py <chemin_photo> [dossier_sortie]")
        print("Exemple: python split_photo.py photo.jpg")
        print("Exemple: python split_photo.py photo.jpg ./output")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(input_path):
        print(f"❌ Erreur: le fichier {input_path} n'existe pas")
        sys.exit(1)
    
    split_photo_2_3_to_3_4(input_path, output_dir)