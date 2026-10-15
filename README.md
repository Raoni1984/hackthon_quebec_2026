# Saint-Roch en Réseau 🗺️

MVP de démonstration pour le hackathon — PWA avec carte interactive, système de points et espace commerçant.

## Stack technique

| Couche | Technologie |
|--------|-------------|
| Base de données | Supabase (PostgreSQL hébergé, API REST auto-générée) |
| Import de données | Python + pandas |
| API métier | FastAPI (Python) |
| Frontend | PWA (React + Leaflet — équipe frontend) |

## Structure du projet

```
hackthon_quebec/
├── backend/
│   ├── api/          # FastAPI — logique métier (points, récompenses)
│   ├── data/         # Fichiers sources XLS/CSV/GeoJSON
│   └── scripts/      # Import pandas → Supabase
├── supabase/
│   └── schema.sql    # Schéma complet à exécuter dans Supabase
└── README.md
```

## Démarrage rapide

### 1. Créer le projet Supabase
1. Aller sur [supabase.com](https://supabase.com) → New project
2. Copier l'URL et la clé `anon` depuis Settings → API
3. Créer le fichier `backend/.env` avec ces valeurs

### 2. Créer les tables
Exécuter `supabase/schema.sql` dans l'éditeur SQL de Supabase.

### 3. Importer les données
```bash
cd backend
pip install -r requirements.txt
python scripts/import_data.py
```

### 4. Lancer l'API
```bash
cd backend/api
uvicorn main:app --reload
```

## Démo MVP — scénario principal

1. Citoyen ouvre la carte → voit les commerces/organismes de Saint-Roch
2. Clique sur un lieu → fiche détaillée + événements
3. "J'y suis allé" → gagne des points (simulé)
4. Consulte son portefeuille → échange contre une récompense
5. Commerçant → panneau simple pour modifier sa fiche / créer un événement
