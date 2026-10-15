-- ============================================================
-- Saint-Roch en Réseau — Schéma SQL (MVP Hackathon)
-- Coller et exécuter dans l'éditeur SQL de Supabase
-- Pas d'auth, pas de RLS — démonstration uniquement
-- ============================================================

-- --------------------------------------------------------
-- 1. UTILISATEURS (citoyens + commerçants, simplifié)
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name TEXT NOT NULL,
    email       TEXT UNIQUE,
    role        TEXT NOT NULL DEFAULT 'citizen'
                CHECK (role IN ('citizen', 'merchant', 'admin')),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Utilisateurs de démo
INSERT INTO users (display_name, email, role) VALUES
    ('Alice Citoyen',      'alice@demo.com',     'citizen'),
    ('Bob Commerçant',     'bob@demo.com',       'merchant'),
    ('Café Le Moine',      'moine@demo.com',     'merchant'),
    ('Librairie Pantoute', 'pantoute@demo.com',  'merchant');


-- --------------------------------------------------------
-- 2. ORGANISATIONS (commerces, restaurants, organismes)
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS organizations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    type        TEXT NOT NULL DEFAULT 'commerce'
                CHECK (type IN ('commerce', 'restaurant', 'organisme', 'service', 'culture')),
    description TEXT,
    address     TEXT,
    phone       TEXT,
    website     TEXT,
    logo_url    TEXT,
    verified    BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Données de démo — Saint-Roch, Québec
INSERT INTO organizations (name, type, description, address, verified) VALUES
    ('Café Le Moine Échanson',  'restaurant', 'Café artisanal, brunchs et sandwichs faits maison.',        '585 rue Saint-Jean, Québec', TRUE),
    ('Librairie Pantoute',      'culture',    'Librairie indépendante généraliste, coups de cœur des libraires.', '286 rue Saint-Joseph E, Québec', TRUE),
    ('L''Gros Luxe',            'restaurant', 'Burgers et cocktails dans une ambiance décontractée.',       '615 rue Saint-Joseph E, Québec', TRUE),
    ('Centre Dina-Bélanger',    'organisme',  'Centre communautaire, activités pour tous les âges.',        '155 rue Saint-Olivier, Québec', TRUE),
    ('Benjo',                   'commerce',   'Magasin de jouets créatifs et éducatifs pour enfants.',      '550 rue Saint-Joseph E, Québec', TRUE),
    ('Chez Victor',             'restaurant', 'Burgers signatures depuis 1980.',                            '145 rue Saint-Jean, Québec', TRUE);


-- --------------------------------------------------------
-- 3. POINTS D'INTÉRÊT (tout ce qui s'affiche sur la carte)
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS points_of_interest (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    name            TEXT NOT NULL,
    category        TEXT NOT NULL DEFAULT 'autre'
                    CHECK (category IN ('restaurant', 'commerce', 'culture', 'parc', 'art', 'service', 'organisme', 'autre')),
    description     TEXT,
    address         TEXT,
    latitude        DOUBLE PRECISION NOT NULL,
    longitude       DOUBLE PRECISION NOT NULL,
    image_url       TEXT,
    source          TEXT DEFAULT 'manuel',   -- 'manuel', 'import_csv', 'opendata'
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Données géolocalisées de Saint-Roch (coordonnées réelles)
INSERT INTO points_of_interest (name, category, description, address, latitude, longitude, source, organization_id)
SELECT
    o.name, o.type::TEXT, o.description, o.address,
    lat, lon, 'manuel', o.id
FROM organizations o
JOIN (VALUES
    ('Café Le Moine Échanson',  46.8143,  -71.2156),
    ('Librairie Pantoute',      46.8138,  -71.2175),
    ('L''Gros Luxe',            46.8135,  -71.2148),
    ('Centre Dina-Bélanger',    46.8122,  -71.2183),
    ('Benjo',                   46.8137,  -71.2162),
    ('Chez Victor',             46.8150,  -71.2211)
) AS coords(nom, lat, lon) ON o.name = coords.nom;

-- Lieux publics (sans organisation)
INSERT INTO points_of_interest (name, category, description, address, latitude, longitude, source) VALUES
    ('Jardin de Saint-Roch',    'parc',   'Parc urbain animé au cœur du quartier.',   'rue de la Couronne, Québec', 46.8130, -71.2170, 'manuel'),
    ('Fresque du quartier',     'art',    'Murale collective illustrant l''histoire de Saint-Roch.', 'rue Saint-Joseph E', 46.8132, -71.2145, 'manuel'),
    ('Bibliothèque Gabrielle-Roy', 'culture', 'Bibliothèque publique moderne avec espace jeunesse.', '350 rue Saint-Joseph E, Québec', 46.8140, -71.2190, 'manuel');


-- --------------------------------------------------------
-- 4. ÉVÉNEMENTS
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    poi_id          UUID REFERENCES points_of_interest(id) ON DELETE SET NULL,
    title           TEXT NOT NULL,
    description     TEXT,
    starts_at       TIMESTAMPTZ NOT NULL,
    ends_at         TIMESTAMPTZ,
    points_reward   INTEGER DEFAULT 0,  -- points gagnés en participant
    status          TEXT DEFAULT 'published'
                    CHECK (status IN ('draft', 'published', 'cancelled')),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Événements de démo

INSERT INTO events (title, description, starts_at, ends_at, points_reward, status, organization_id)
VALUES
    ('Dégustation de cafés du monde',    'Découvrez 5 origines de café, animée par le torréfacteur.',
     NOW() + '3 days',  NOW() + '3 days 2 hours',  50,  'published',
     (SELECT id FROM organizations WHERE name = 'Café Le Moine Échanson')),

    ('Séance de dédicaces — auteur local', 'Rencontrez Marie-Claude Paradis pour son nouveau roman.',
     NOW() + '5 days',  NOW() + '5 days 3 hours',  75,  'published',
     (SELECT id FROM organizations WHERE name = 'Librairie Pantoute')),

    ('Happy hour citoyen',               '20 % de rabais sur les burgers pour les membres du réseau.',
     NOW() + '1 day',   NOW() + '1 day 4 hours',   30,  'published',
     (SELECT id FROM organizations WHERE name = 'L''Gros Luxe')),

    ('Atelier peinture communautaire',   'Créez une toile collective avec des artistes du quartier.',
     NOW() + '7 days',  NOW() + '7 days 3 hours',  100, 'published',
     (SELECT id FROM organizations WHERE name = 'Centre Dina-Bélanger'));


-- --------------------------------------------------------
-- 5. FAVORIS
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS favorites (
    id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    poi_id  UUID REFERENCES points_of_interest(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, poi_id)
);


-- --------------------------------------------------------
-- 6. PORTEFEUILLE & TRANSACTIONS DE POINTS
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS wallets (
    id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    balance INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Créer un portefeuille pour chaque utilisateur de démo
INSERT INTO wallets (user_id, balance)
SELECT id, 
    CASE role WHEN 'citizen' THEN 120 ELSE 0 END
FROM users;

CREATE TABLE IF NOT EXISTS point_transactions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    amount          INTEGER NOT NULL,        -- positif = gain, négatif = dépense
    transaction_type TEXT NOT NULL
                    CHECK (transaction_type IN ('visit', 'event', 'reward', 'bonus', 'admin')),
    description     TEXT,
    reference_id    UUID,                   -- poi_id, event_id ou reward_id
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Historique de démo pour Alice
INSERT INTO point_transactions (user_id, amount, transaction_type, description)
SELECT id, 50, 'visit', 'Visite — Café Le Moine Échanson' FROM users WHERE email = 'alice@demo.com';
INSERT INTO point_transactions (user_id, amount, transaction_type, description)
SELECT id, 75, 'event', 'Participation — Dégustation de cafés du monde' FROM users WHERE email = 'alice@demo.com';
INSERT INTO point_transactions (user_id, amount, transaction_type, description)
SELECT id, -5, 'reward', 'Échange — Café gratuit chez Le Moine' FROM users WHERE email = 'alice@demo.com';


-- --------------------------------------------------------
-- 7. RÉCOMPENSES & ÉCHANGES
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS rewards (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    description     TEXT,
    cost_points     INTEGER NOT NULL CHECK (cost_points > 0),
    stock           INTEGER DEFAULT NULL,    -- NULL = illimité
    valid_until     DATE,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO rewards (title, description, cost_points, organization_id) VALUES
    ('Café gratuit',          '1 café filtre ou espresso offert.',              50,
     (SELECT id FROM organizations WHERE name = 'Café Le Moine Échanson')),
    ('10 % sur ta commande',  'Rabais de 10 % sur tout le menu.',               75,
     (SELECT id FROM organizations WHERE name = 'L''Gros Luxe')),
    ('Livre à -5 $',          '5 $ de rabais sur tout achat en librairie.',      100,
     (SELECT id FROM organizations WHERE name = 'Librairie Pantoute')),
    ('Jouet surprise',        'Un petit jouet surprise pour les enfants.',        60,
     (SELECT id FROM organizations WHERE name = 'Benjo'));

CREATE TABLE IF NOT EXISTS redemptions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    reward_id   UUID REFERENCES rewards(id) ON DELETE CASCADE,
    code        TEXT UNIQUE DEFAULT substring(md5(random()::TEXT), 1, 8),
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);


-- --------------------------------------------------------
-- 8. VUE UTILE — carte enrichie pour le frontend
-- --------------------------------------------------------
CREATE OR REPLACE VIEW v_map_points AS
SELECT
    p.id,
    p.name,
    p.category,
    p.description,
    p.address,
    p.latitude,
    p.longitude,
    p.image_url,
    p.is_active,
    o.id           AS org_id,
    o.name         AS org_name,
    o.type         AS org_type,
    o.phone        AS org_phone,
    o.website      AS org_website,
    o.logo_url     AS org_logo,
    -- Nombre d'événements à venir
    (SELECT COUNT(*) FROM events e
     WHERE e.organization_id = o.id
       AND e.starts_at > NOW()
       AND e.status = 'published') AS upcoming_events,
    -- Nombre de récompenses disponibles
    (SELECT COUNT(*) FROM rewards r
     WHERE r.organization_id = o.id
       AND r.is_active = TRUE) AS available_rewards
FROM points_of_interest p
LEFT JOIN organizations o ON p.organization_id = o.id
WHERE p.is_active = TRUE;
