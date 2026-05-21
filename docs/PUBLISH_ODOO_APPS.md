# Publier BI Realtime sur Odoo Apps

## Deux méthodes

| Méthode | URL / action |
|---------|----------------|
| **ZIP** (simple) | [apps.odoo.com/apps/upload](https://apps.odoo.com/apps/upload) → `dist/bi_realtime.zip` |
| **Dépôt Git** | Branche `17.0` avec `bi_realtime/` **à la racine** (voir ci-dessous) |

---

## Méthode Git — format URL Odoo 17

```
ssh://git@github.com/Akremjs/BI-Realtime.git#17.0
```

Règles Odoo :
- Un dossier **par module à la racine** du dépôt → `bi_realtime/` (pas `odoo-module/bi_realtime/`)
- Le suffixe `#17.0` = nom de branche **identique** à la série Odoo (17.0, pas `main`)

### Message « Ce dépôt et cette branche sont déjà enregistrés »

C’est **normal** : ne pas ré-enregistrer l’URL. Aller sur la fiche du module → **Balayage / Scan** ou **Synchroniser** le dépôt déjà lié.

Formats URL acceptés (identiques en pratique) :
```
ssh://git@github.com/Akremjs/BI-Realtime.git#17.0
git@github.com:Akremjs/BI-Realtime.git#17.0
```
- Pas d’espace, pas de `https://`, branche exactement `17.0`
- Dépôt **public** ou clé SSH OdooApps autorisée sur GitHub (paramètres repo → Deploy keys / collaborators)

### Créer la branche `17.0` sur GitHub

```bash
cd ~/pfe-bi-odoo
bash scripts/prepare_odoo_apps_git_branch.sh
git push -u apps 17.0
```

Puis sur [apps.odoo.com](https://apps.odoo.com) → enregistrer l’URL Git ci-dessus.

La branche `main` conserve tout le projet PFE (Docker, Kafka, etc.).

---

## 1. Générer le ZIP

```bash
cd ~/pfe-bi-odoo
bash scripts/package_odoo_module.sh
```

Fichier produit : **`dist/bi_realtime.zip`**

Structure attendue dans le ZIP :
```
bi_realtime/
  __manifest__.py
  static/description/icon.png
  static/description/index.html
  ...
```

## 2. Compte vendeur Odoo Apps

1. Aller sur [https://apps.odoo.com/apps/upload](https://apps.odoo.com/apps/upload)
2. Se connecter avec un compte Odoo.com
3. Compléter le profil **vendor** si demandé (première soumission)

## 3. Téléverser le module

1. **Upload** → choisir `dist/bi_realtime.zip`
2. Vérifier la détection : nom technique `bi_realtime`, version `17.0.x`
3. Renseigner :
   - **Price** : 0 (gratuit) ou votre tarif
   - **Currency** : EUR
   - **Support email** : votre email pro
   - **Live test URL** : optionnel (URL démo Odoo si vous en avez une)

## 4. Régénérer logo / bannière (optionnel)

```bash
cd bi_realtime/static/description
python3 render_icon.py    # icon.png 256×256
python3 render_banner.py  # banner.png 560×280
```

Source vectorielle : `logo.svg` (couleurs marque `#6366f1`, `#10b981`).

## 5. Règles importantes (validation Odoo)

| Règle | Détail |
|-------|--------|
| Langue | Description `index.html` en **anglais** ✅ |
| Icône | `static/description/icon.png` (PNG réel) ✅ |
| Grande image Apps (cadre gauche) | `main_screenshot.png` + clé `images` dans `__manifest__.py` ✅ |
| Pas de secrets | Pas de `.env`, clés API dans le code |
| Licence | `LGPL-3` dans le manifest ✅ |
| Autonome | Le module doit fonctionner **sans** Docker/Kafka |

## 6. Après publication

- Tester l’install depuis Apps sur une base Odoo 17 vierge
- Répondre aux retours des validateurs Odoo (délai : quelques jours à semaines)
- Pousser les mises à jour : nouveau ZIP + bump version dans `__manifest__.py`

## 7. Mise à jour version

Dans `__manifest__.py` :
```python
'version': '17.0.1.0.1',  # incrémenter à chaque soumission
```

Puis :
```bash
bash scripts/package_odoo_module.sh
# Re-upload sur apps.odoo.com
```

## 8. GitHub (recommandé)

Garder le repo public pour la doc et le support :
https://github.com/Akremjs/BI-Realtime-Dashboard-pour-Odoo
