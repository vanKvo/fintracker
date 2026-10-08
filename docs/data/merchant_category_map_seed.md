-- ============================================================================
-- merchant_category_map_seed.sql
--
-- Starting data for the merchant_category_map table (see spec:
-- DP-LEDGER-CATEGORIES-3 resolution chain, step 3 — merchant text matching
-- for PDF/raw-text transactions with no bank-provided category).
--
-- Schema assumed:
--   merchant_category_map (
--     pattern     text UNIQUE,   -- regex, applied to normalized transaction text
--     match_type  text,          -- 'regex' | 'contains'
--     code        text,          -- SYSTEM category code (see DP-LEDGER-CATEGORIES-1)
--     priority    int,           -- lower = matched first when multiple patterns hit
--     active      bool
--   )
--
-- Normalization assumed before matching: uppercase, collapse whitespace,
-- keep punctuation (patterns below rely on it). Apply the SAME normalize()
-- function at match time as documented alongside this seed — if it changes,
-- every pattern here needs re-validation.
--
-- Patterns are deliberately narrow. Ambiguous merchants (Target, Walmart,
-- Costco outside the warehouse-club sense, gas-station convenience-store
-- purchases, etc.) are intentionally left OUT — a wrong guess is worse than
-- falling through to "uncategorized" and letting the user pick.
--
-- Re-runnable: ON CONFLICT (pattern) DO UPDATE, so this file can be reapplied
-- after edits without creating duplicates. Note that DO UPDATE overwrites
-- match_type/code/priority/active, so this file is the source of truth for them.
--
-- Codes must be existing Ledger SYSTEM category codes (e.g. healthcare,
-- food-and-drink); the Data Pipeline's seed converter rejects unknown codes.
-- ============================================================================

INSERT INTO merchant_category_map (pattern, match_type, code, priority, active)
VALUES

-- ---------------------------------------------------------------------------
-- GROCERIES
-- ---------------------------------------------------------------------------
('TRADER JOE''?S',            'regex',    'groceries', 10, true),
('WHOLEFDS',                  'contains', 'groceries', 10, true),
('WHOLE FOODS',               'contains', 'groceries', 10, true),
('KROGER',                    'contains', 'groceries', 10, true),
('SAFEWAY',                   'contains', 'groceries', 10, true),
('PUBLIX',                    'contains', 'groceries', 10, true),
('ALDI',                      'contains', 'groceries', 10, true),
('COSTCO WHSE',               'contains', 'groceries', 10, true),
('SPROUTS FARMERS',           'contains', 'groceries', 10, true),
('HARRIS TEETER',             'contains', 'groceries', 10, true),
('GIANT FOOD',                'contains', 'groceries', 10, true),
('STOP & SHOP',                'contains', 'groceries', 10, true),
('WEGMANS',                   'contains', 'groceries', 10, true),
('H-E-B',                     'contains', 'groceries', 10, true),
('MEIJER',                    'contains', 'groceries', 10, true),
('ALBERTSONS',                'contains', 'groceries', 10, true),
('VONS',                      'contains', 'groceries', 10, true),
('FOOD LION',                 'contains', 'groceries', 10, true),
('INSTACART',                 'contains', 'groceries', 15, true),

-- ---------------------------------------------------------------------------
-- DINING (restaurants, cafes, fast food, food delivery)
-- ---------------------------------------------------------------------------
('STARBUCKS',                 'contains', 'food-and-drink', 10, true),
('CHIPOTLE',                  'contains', 'food-and-drink', 10, true),
('MCDONALD''?S',              'regex',    'food-and-drink', 10, true),
('PANERA',                    'contains', 'food-and-drink', 10, true),
('DUNKIN',                    'contains', 'food-and-drink', 10, true),
('SUBWAY',                    'contains', 'food-and-drink', 10, true),
('CHICK-FIL-A',               'contains', 'food-and-drink', 10, true),
('DOMINO''?S',                'regex',    'food-and-drink', 10, true),
('PIZZA HUT',                 'contains', 'food-and-drink', 10, true),
('TACO BELL',                 'contains', 'food-and-drink', 10, true),
('WENDY''?S',                 'regex',    'food-and-drink', 10, true),
('BURGER KING',               'contains', 'food-and-drink', 10, true),
('SHAKE SHACK',               'contains', 'food-and-drink', 10, true),
('FIVE GUYS',                 'contains', 'food-and-drink', 10, true),
('OLIVE GARDEN',              'contains', 'food-and-drink', 10, true),
('SQ \*',                     'regex',    'food-and-drink', 25, true),   -- Square POS, mostly cafes/small food — low priority, broad
('TST\*',                     'regex',    'food-and-drink', 25, true),   -- Toast POS, restaurants — low priority, broad
('UBER \*EATS',               'regex',    'food-and-drink', 5,  true),   -- must beat generic UBER pattern below
('UBEREATS',                  'contains', 'food-and-drink', 5,  true),
('DOORDASH',                  'contains', 'food-and-drink', 10, true),
('GRUBHUB',                   'contains', 'food-and-drink', 10, true),
('POSTMATES',                 'contains', 'food-and-drink', 10, true),

-- ---------------------------------------------------------------------------
-- TRANSPORTATION (rideshare, gas, parking, transit, tolls)
-- ---------------------------------------------------------------------------
('UBER \*TRIP',               'regex',    'transportation', 5,  true),  -- specific, beats generic UBER
('LYFT',                      'contains', 'transportation', 10, true),
('SHELL OIL',                 'contains', 'transportation', 10, true),
('CHEVRON',                   'contains', 'transportation', 10, true),
('EXXON',                     'contains', 'transportation', 10, true),
('MOBIL',                     'contains', 'transportation', 10, true),
('BP#',                       'contains', 'transportation', 10, true),
('SPEEDWAY',                  'contains', 'transportation', 10, true),
('CIRCLE K',                  'contains', 'transportation', 15, true),  -- often also sells snacks; lower confidence
('AMTRAK',                    'contains', 'transportation', 10, true),
('EZPASS',                    'contains', 'transportation', 10, true),
('E-ZPASS',                   'contains', 'transportation', 10, true),
('MTA\*',                     'regex',    'transportation', 10, true),
('PARKMOBILE',                'contains', 'transportation', 10, true),
('SPOTHERO',                  'contains', 'transportation', 10, true),
('DELTA AIR',                 'contains', 'transportation', 10, true),
('SOUTHWES ',                 'contains', 'transportation', 10, true),  -- statements often show "SOUTHWES " (truncated)
('UNITED AIR',                'contains', 'transportation', 10, true),

-- ---------------------------------------------------------------------------
-- UTILITIES / SUBSCRIPTIONS (streaming, phone, internet, cloud)
-- ---------------------------------------------------------------------------
('NETFLIX\.COM',              'regex',    'subscriptions', 10, true),
('SPOTIFY',                   'contains', 'subscriptions', 10, true),
('HULU',                      'contains', 'subscriptions', 10, true),
('DISNEY PLUS',               'contains', 'subscriptions', 10, true),
('DISNEYPLUS',                'contains', 'subscriptions', 10, true),
('APPLE\.COM/BILL',           'regex',    'subscriptions', 10, true),
('GOOGLE \*',                 'regex',    'subscriptions', 20, true),   -- broad, low priority (covers many Google services)
('AMAZON PRIME',              'contains', 'subscriptions', 10, true),
('COMCAST',                   'contains', 'utilities', 10, true),
('XFINITY',                   'contains', 'utilities', 10, true),
('AT&T\*',                    'regex',    'utilities', 10, true),
('VERIZON WRLS',              'contains', 'utilities', 10, true),
('T-MOBILE',                  'contains', 'utilities', 10, true),
('SPECTRUM',                  'contains', 'utilities', 10, true),

-- ---------------------------------------------------------------------------
-- SHOPPING (general retail, online marketplaces)
-- ---------------------------------------------------------------------------
('AMZN MKTP',                 'contains', 'shopping', 20, true),
('AMAZON\.COM\*',             'regex',    'shopping', 20, true),
('TARGET\.COM',               'regex',    'shopping', 15, true),   -- only .com; bare TARGET excluded (ambiguous, sells groceries too)
('BEST BUY',                  'contains', 'shopping', 10, true),
('HOME DEPOT',                'contains', 'shopping', 10, true),
('LOWE''?S',                  'regex',    'shopping', 10, true),
('IKEA',                      'contains', 'shopping', 10, true),
('ETSY',                      'contains', 'shopping', 10, true),

-- ---------------------------------------------------------------------------
-- HEALTH / PERSONAL CARE
-- ---------------------------------------------------------------------------
('CVS/PHARMACY',              'contains', 'healthcare', 10, true),
('WALGREENS',                 'contains', 'healthcare', 10, true),
('RITE AID',                  'contains', 'healthcare', 10, true),
('GNC ',                      'contains', 'healthcare', 10, true)

ON CONFLICT (pattern) DO UPDATE SET
  match_type = EXCLUDED.match_type,
  code       = EXCLUDED.code,
  priority   = EXCLUDED.priority,
  active     = EXCLUDED.active;