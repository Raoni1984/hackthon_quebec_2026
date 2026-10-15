"""
Saint-Roch en Réseau — API FastAPI
MVP Hackathon — pas d'authentification, démonstration uniquement

Endpoints principaux :
  GET  /api/map          → tous les POIs pour la carte
  GET  /api/pois/{id}    → détail d'un lieu + événements + récompenses
  GET  /api/events       → événements à venir
  GET  /api/rewards      → toutes les récompenses disponibles
  POST /api/visits       → simuler une visite → gagner des points
  GET  /api/wallet/{uid} → portefeuille d'un utilisateur
  POST /api/redeem       → échanger des points contre une récompense
  GET  /api/users        → liste des utilisateurs (démo)
  POST /api/merchants/poi       → commerçant crée/modifie un POI
  POST /api/merchants/events    → commerçant crée un événement
  POST /api/merchants/rewards   → commerçant crée une récompense
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(
    title="Saint-Roch en Réseau API",
    description="API MVP pour le hackathon — données du quartier Saint-Roch, Québec",
    version="0.1.0",
)

# CORS — permet au frontend PWA d'appeler l'API depuis n'importe quelle origine
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Modèles Pydantic ────────────────────────────────────────────────────────

class VisitRequest(BaseModel):
    user_id: str
    poi_id: str
    points_earned: int = 50  # valeur par défaut pour la démo

class RedeemRequest(BaseModel):
    user_id: str
    reward_id: str

class POICreate(BaseModel):
    name: str
    category: str
    description: Optional[str] = None
    address: Optional[str] = None
    latitude: float
    longitude: float
    organization_id: Optional[str] = None

class EventCreate(BaseModel):
    organization_id: str
    title: str
    description: Optional[str] = None
    starts_at: str          # ISO 8601 ex: "2026-10-20T18:00:00"
    ends_at: Optional[str] = None
    points_reward: int = 0

class RewardCreate(BaseModel):
    organization_id: str
    title: str
    description: Optional[str] = None
    cost_points: int


# ── Endpoints carte & lieux ─────────────────────────────────────────────────

@app.get("/api/map", summary="Tous les points d'intérêt pour la carte")
def get_map_points(category: Optional[str] = None):
    """
    Retourne tous les POIs actifs avec info d'organisation, événements et récompenses.
    Filtrage optionnel par catégorie : ?category=restaurant
    """
    query = supabase.table("v_map_points").select("*")
    if category:
        query = query.eq("category", category)
    result = query.execute()
    return {"points": result.data, "total": len(result.data)}


@app.get("/api/pois/{poi_id}", summary="Détail d'un lieu")
def get_poi_detail(poi_id: str):
    """Retourne le détail d'un lieu + ses événements à venir + ses récompenses."""
    # Infos du POI
    poi = supabase.table("points_of_interest").select("*").eq("id", poi_id).single().execute()
    if not poi.data:
        raise HTTPException(status_code=404, detail="Lieu introuvable")

    events = []
    rewards = []

    if poi.data.get("organization_id"):
        org_id = poi.data["organization_id"]

        # Événements à venir de cette organisation
        events = supabase.table("events")\
            .select("*")\
            .eq("organization_id", org_id)\
            .eq("status", "published")\
            .gte("starts_at", "now()")\
            .order("starts_at")\
            .execute().data

        # Récompenses disponibles
        rewards = supabase.table("rewards")\
            .select("*")\
            .eq("organization_id", org_id)\
            .eq("is_active", True)\
            .execute().data

    return {
        "poi": poi.data,
        "events": events,
        "rewards": rewards,
    }


# ── Endpoints événements & récompenses ─────────────────────────────────────

@app.get("/api/events", summary="Événements à venir")
def get_events(limit: int = 20):
    """Liste des événements publiés à venir, triés par date."""
    result = supabase.table("events")\
        .select("*, organizations(name, logo_url)")\
        .eq("status", "published")\
        .gte("starts_at", "now()")\
        .order("starts_at")\
        .limit(limit)\
        .execute()
    return {"events": result.data}


@app.get("/api/rewards", summary="Récompenses disponibles")
def get_rewards():
    """Toutes les récompenses actives, avec l'organisation associée."""
    result = supabase.table("rewards")\
        .select("*, organizations(name, logo_url)")\
        .eq("is_active", True)\
        .execute()
    return {"rewards": result.data}


# ── Endpoints portefeuille & points ────────────────────────────────────────

@app.get("/api/wallet/{user_id}", summary="Portefeuille d'un utilisateur")
def get_wallet(user_id: str):
    """Retourne le solde et l'historique des transactions."""
    wallet = supabase.table("wallets")\
        .select("*")\
        .eq("user_id", user_id)\
        .single()\
        .execute()

    if not wallet.data:
        raise HTTPException(status_code=404, detail="Portefeuille introuvable")

    transactions = supabase.table("point_transactions")\
        .select("*")\
        .eq("user_id", user_id)\
        .order("created_at", desc=True)\
        .limit(20)\
        .execute()

    return {
        "balance": wallet.data["balance"],
        "transactions": transactions.data,
    }


@app.post("/api/visits", summary="Enregistrer une visite → gagner des points")
def record_visit(req: VisitRequest):
    """
    Simule une visite d'un lieu.
    Crédite les points dans le portefeuille et crée une transaction.
    Pour la démo, n'importe quel user_id valide peut appeler cet endpoint.
    """
    # Vérifier que le POI existe
    poi = supabase.table("points_of_interest").select("name").eq("id", req.poi_id).single().execute()
    if not poi.data:
        raise HTTPException(status_code=404, detail="Lieu introuvable")

    # Créditer les points
    wallet = supabase.table("wallets").select("balance").eq("user_id", req.user_id).single().execute()
    if not wallet.data:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    new_balance = wallet.data["balance"] + req.points_earned
    supabase.table("wallets").update({"balance": new_balance}).eq("user_id", req.user_id).execute()

    # Enregistrer la transaction
    supabase.table("point_transactions").insert({
        "user_id": req.user_id,
        "amount": req.points_earned,
        "transaction_type": "visit",
        "description": f"Visite — {poi.data['name']}",
        "reference_id": req.poi_id,
    }).execute()

    return {
        "success": True,
        "points_earned": req.points_earned,
        "new_balance": new_balance,
        "message": f"+{req.points_earned} points pour ta visite chez {poi.data['name']} 🎉",
    }


@app.post("/api/redeem", summary="Échanger des points contre une récompense")
def redeem_reward(req: RedeemRequest):
    """
    Échange des points contre une récompense.
    Vérifie que le solde est suffisant, génère un code unique.
    """
    # Vérifier la récompense
    reward = supabase.table("rewards").select("*").eq("id", req.reward_id).eq("is_active", True).single().execute()
    if not reward.data:
        raise HTTPException(status_code=404, detail="Récompense introuvable ou inactive")

    cost = reward.data["cost_points"]

    # Vérifier le solde
    wallet = supabase.table("wallets").select("balance").eq("user_id", req.user_id).single().execute()
    if not wallet.data:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    balance = wallet.data["balance"]
    if balance < cost:
        raise HTTPException(status_code=400, detail=f"Solde insuffisant ({balance} pts, besoin de {cost} pts)")

    # Débiter les points
    new_balance = balance - cost
    supabase.table("wallets").update({"balance": new_balance}).eq("user_id", req.user_id).execute()

    # Transaction
    supabase.table("point_transactions").insert({
        "user_id": req.user_id,
        "amount": -cost,
        "transaction_type": "reward",
        "description": f"Échange — {reward.data['title']}",
        "reference_id": req.reward_id,
    }).execute()

    # Créer le code d'échange
    redemption = supabase.table("redemptions").insert({
        "user_id": req.user_id,
        "reward_id": req.reward_id,
    }).execute()

    return {
        "success": True,
        "code": redemption.data[0]["code"],
        "reward": reward.data["title"],
        "cost": cost,
        "new_balance": new_balance,
        "message": f"✅ Récompense obtenue ! Présente le code en caisse.",
    }


# ── Endpoints commerçant (espace professionnel) ─────────────────────────────

@app.get("/api/users", summary="Liste des utilisateurs (démo)")
def get_users():
    """Retourne tous les utilisateurs avec leur solde — pour la démo."""
    users = supabase.table("users").select("*, wallets(balance)").execute()
    return {"users": users.data}


@app.get("/api/merchants/{org_id}/dashboard", summary="Tableau de bord commerçant")
def merchant_dashboard(org_id: str):
    """Vue d'ensemble pour un commerçant : fiche, événements, récompenses."""
    org = supabase.table("organizations").select("*").eq("id", org_id).single().execute()
    if not org.data:
        raise HTTPException(status_code=404, detail="Organisation introuvable")

    events = supabase.table("events").select("*").eq("organization_id", org_id).order("starts_at", desc=True).execute()
    rewards = supabase.table("rewards").select("*").eq("organization_id", org_id).execute()

    return {
        "organization": org.data,
        "events": events.data,
        "rewards": rewards.data,
    }


@app.post("/api/merchants/poi", summary="Créer ou mettre à jour un POI")
def create_poi(poi: POICreate):
    """Permet à un commerçant d'ajouter un lieu sur la carte."""
    result = supabase.table("points_of_interest").insert({
        "name": poi.name,
        "category": poi.category,
        "description": poi.description,
        "address": poi.address,
        "latitude": poi.latitude,
        "longitude": poi.longitude,
        "organization_id": poi.organization_id,
        "source": "merchant",
    }).execute()
    return {"success": True, "poi": result.data[0]}


@app.post("/api/merchants/events", summary="Créer un événement")
def create_event(ev: EventCreate):
    """Permet à un commerçant de publier un événement."""
    result = supabase.table("events").insert({
        "organization_id": ev.organization_id,
        "title": ev.title,
        "description": ev.description,
        "starts_at": ev.starts_at,
        "ends_at": ev.ends_at,
        "points_reward": ev.points_reward,
        "status": "published",
    }).execute()
    return {"success": True, "event": result.data[0]}


@app.post("/api/merchants/rewards", summary="Créer une récompense")
def create_reward(r: RewardCreate):
    """Permet à un commerçant d'ajouter une offre échangeable en points."""
    result = supabase.table("rewards").insert({
        "organization_id": r.organization_id,
        "title": r.title,
        "description": r.description,
        "cost_points": r.cost_points,
        "is_active": True,
    }).execute()
    return {"success": True, "reward": result.data[0]}


# ── Santé ────────────────────────────────────────────────────────────────────

@app.get("/", summary="Santé de l'API")
def root():
    return {
        "api": "Saint-Roch en Réseau",
        "version": "0.1.0",
        "status": "ok",
        "docs": "/docs",
    }
