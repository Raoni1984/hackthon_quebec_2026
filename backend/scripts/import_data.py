"""
Script d'import de données — Saint-Roch en Réseau
Importe des fichiers XLS/CSV/GeoJSON dans Supabase via pandas

Usage:
    python import_data.py --source data/commerces.xlsx --type poi
    python import_data.py --source data/evenements.csv --type events
    python import_data.py --source data/lieux.geojson  --type geojson
"""

import argparse
import json
import os
import sys

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # clé service pour l'import

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ── Colonnes attendues par type d'import ───────────────────────────────────

POI_COLUMNS = {
    # Noms possibles dans le fichier source → nom dans la BD
    "nom": "name",
    "name": "name",
    "nomcommerce": "name",
    "categorie": "category",
    "category": "category",
    "type": "category",
    "description": "description",
    "adresse": "address",
    "address": "address",
    "latitude": "latitude",
    "lat": "latitude",
    "longitude": "longitude",
    "lon": "longitude",
    "lng": "longitude",
    "long": "longitude",
}

CATEGORY_MAP = {
    # Normalisation des catégories
    "café": "restaurant",
    "coffee": "restaurant",
    "resto": "restaurant",
    "bar": "restaurant",
    "librairie": "culture",
    "bibliothèque": "culture",
    "musée": "culture",
    "magasin": "commerce",
    "boutique": "commerce",
    "épicerie": "commerce",
    "parc": "parc",
    "jardin": "parc",
    "oeuvre": "art",
    "mural": "art",
    "murale": "art",
    "organisme": "organisme",
    "communautaire": "organisme",
    "santé": "service",
    "pharmacie": "service",
}

VALID_CATEGORIES = {"restaurant", "commerce", "culture", "parc", "art", "service", "organisme", "autre"}


def normalize_category(raw: str) -> str:
    """Normalise une catégorie brute vers les valeurs acceptées par la BD."""
    if not raw:
        return "autre"
    raw_lower = str(raw).lower().strip()
    for key, val in CATEGORY_MAP.items():
        if key in raw_lower:
            return val
    return raw_lower if raw_lower in VALID_CATEGORIES else "autre"


def load_dataframe(filepath: str) -> pd.DataFrame:
    """Charge un fichier XLS, XLSX, CSV ou GeoJSON en DataFrame."""
    ext = os.path.splitext(filepath)[1].lower()

    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(filepath)
    elif ext == ".csv":
        # Essai UTF-8 puis latin-1 (fréquent pour les données québécoises)
        try:
            df = pd.read_csv(filepath, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(filepath, encoding="latin-1")
    elif ext == ".geojson" or ext == ".json":
        with open(filepath, encoding="utf-8") as f:
            gj = json.load(f)
        rows = []
        for feat in gj.get("features", []):
            props = feat.get("properties", {})
            coords = feat.get("geometry", {}).get("coordinates", [None, None])
            rows.append({**props, "longitude": coords[0], "latitude": coords[1]})
        df = pd.DataFrame(rows)
    else:
        raise ValueError(f"Format non supporté : {ext}")

    print(f"✅ {len(df)} lignes chargées depuis {filepath}")
    print(f"   Colonnes : {list(df.columns)}")
    return df


def clean_poi_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Nettoie et normalise un DataFrame de points d'intérêt."""
    # Renommer les colonnes vers les noms BD
    df.columns = [c.lower().strip().replace(" ", "").replace("_", "") for c in df.columns]
    rename = {k: v for k, v in POI_COLUMNS.items() if k in df.columns}
    df = df.rename(columns=rename)

    # Vérifier les colonnes obligatoires
    required = ["name", "latitude", "longitude"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Colonnes obligatoires manquantes : {missing}\nColonnes présentes : {list(df.columns)}")

    # Supprimer les lignes sans coordonnées
    before = len(df)
    df = df.dropna(subset=["latitude", "longitude"])
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"])

    # Filtrer les coordonnées hors de Saint-Roch (bbox approximative)
    # Québec : lat 46.75–46.90, lon -71.35 à -71.15
    bbox_filter = (
        (df["latitude"] >= 46.75) & (df["latitude"] <= 46.90) &
        (df["longitude"] >= -71.35) & (df["longitude"] <= -71.15)
    )
    df = df[bbox_filter]
    print(f"   {before - len(df)} lignes supprimées (coords invalides ou hors zone)")

    # Normaliser la catégorie
    if "category" in df.columns:
        df["category"] = df["category"].apply(normalize_category)
    else:
        df["category"] = "autre"

    # Nettoyer le nom
    df["name"] = df["name"].astype(str).str.strip().str.title()

    # Ajouter les champs manquants
    df["source"] = "import_csv"
    df["is_active"] = True
    if "description" not in df.columns:
        df["description"] = None
    if "address" not in df.columns:
        df["address"] = None

    # Garder seulement les colonnes de la BD
    keep = ["name", "category", "description", "address", "latitude", "longitude", "source", "is_active"]
    df = df[[c for c in keep if c in df.columns]]

    print(f"✅ {len(df)} lieux valides après nettoyage")
    return df


def import_pois(filepath: str, dry_run: bool = False):
    """Import principal de points d'intérêt."""
    df = load_dataframe(filepath)
    df = clean_poi_dataframe(df)

    print(f"\n📊 Aperçu des données nettoyées :")
    print(df.head(5).to_string())
    print(f"\nDistribution des catégories :\n{df['category'].value_counts().to_string()}")

    if dry_run:
        print("\n⚠️  Mode dry-run : aucune donnée envoyée à Supabase.")
        return

    records = df.to_dict(orient="records")
    batch_size = 50

    total_inserted = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        result = supabase.table("points_of_interest").insert(batch).execute()
        total_inserted += len(result.data)
        print(f"  → Lot {i // batch_size + 1} : {len(result.data)} lieux insérés")

    print(f"\n✅ Import terminé : {total_inserted} lieux ajoutés à Supabase")


def show_current_data():
    """Affiche un résumé des données actuellement en BD."""
    pois = supabase.table("points_of_interest").select("category", count="exact").execute()
    orgs = supabase.table("organizations").select("type", count="exact").execute()
    events = supabase.table("events").select("status", count="exact").execute()
    print("\n📦 État actuel de la base de données :")
    print(f"  Points d'intérêt : {len(pois.data)}")
    print(f"  Organisations    : {len(orgs.data)}")
    print(f"  Événements       : {len(events.data)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import de données vers Supabase")
    parser.add_argument("--source",  required=False, help="Fichier source (XLS, CSV, GeoJSON)")
    parser.add_argument("--type",    choices=["poi", "geojson"], default="poi")
    parser.add_argument("--dry-run", action="store_true", help="Valider sans importer")
    parser.add_argument("--status",  action="store_true", help="Afficher l'état de la BD")
    args = parser.parse_args()

    if args.status:
        show_current_data()
        sys.exit(0)

    if not args.source:
        parser.print_help()
        sys.exit(1)

    if not os.path.exists(args.source):
        print(f"❌ Fichier introuvable : {args.source}")
        sys.exit(1)

    import_pois(args.source, dry_run=args.dry_run)
