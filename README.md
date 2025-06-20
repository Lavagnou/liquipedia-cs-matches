# Liquipedia Counter-Strike Matches

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

Cette intégration Home Assistant scrape les données du site Liquipedia pour créer des entités avec les informations sur les prochains et derniers matchs des équipes de Counter-Strike que vous souhaitez suivre.

## Fonctionnalités

- Suivi des matchs passés et à venir pour vos équipes CS préférées
- Informations détaillées : date/heure, format du match (Bo1, Bo3, etc.), tournoi, score
- Conversion automatique des fuseaux horaires vers votre fuseau local Home Assistant
- Bouton pour forcer la mise à jour de toutes les équipes
- Traduction française incluse

## Installation

### HACS (recommandé)

1. Assurez-vous d'avoir [HACS](https://hacs.xyz) installé dans votre instance Home Assistant
2. Allez dans HACS → Intégrations → "..."
3. Sélectionnez "Dépôt personnalisé"
4. Ajoutez l'URL de ce dépôt : `https://github.com/Lavagnou/liquipedia-cs-matches`
5. Sélectionnez "Intégration" comme catégorie
6. Cliquez sur "Ajouter"
7. Recherchez "Liquipedia CS Matches" et installez l'intégration
8. Redémarrez Home Assistant

### Installation manuelle

1. Téléchargez le dossier `liquipedia-cs-matches` depuis ce dépôt
2. Copiez-le dans votre dossier `/config/custom_components/`
3. Redémarrez Home Assistant

## Configuration

Ajoutez les équipes que vous souhaitez suivre dans votre fichier `configuration.yaml` :

```yaml
liquipedia_cs:
  teams:
    - name: "Vitality"
      page: "Team_Vitality"
    - name: "NAVI"
      page: "NAVI" 
    - name: "G2"
      page: "G2_Esports"
```

Paramètres :
- `page` : Nom de la page Liquipedia de l'équipe (utilisé dans l'URL)
- `name` : Nom court affiché dans l'interface Home Assistant

## Entités créées

Pour chaque équipe configurée, l'intégration crée 2 capteurs :
- `sensor.liquipedia_cs_<nom_équipe>_next_match` : Prochain match de l'équipe
- `sensor.liquipedia_cs_<nom_équipe>_last_match` : Dernier match de l'équipe

Et un bouton global :
- `button.liquipedia_cs_update_all` : Force la mise à jour de tous les capteurs

## Exemple d'utilisation dans un tableau

```yaml
type: entities
title: Matchs CS
entities:
  - entity: sensor.liquipedia_cs_vitality_next_match
    name: Prochain match Vitality
    secondary_info: attribute.date
  - type: attribute
    entity: sensor.liquipedia_cs_vitality_next_match
    attribute: event
    name: Tournoi
  - type: attribute
    entity: sensor.liquipedia_cs_vitality_next_match
    attribute: format
    name: Format
  - entity: sensor.liquipedia_cs_vitality_last_match
    name: Dernier match Vitality
    secondary_info: attribute.date
  - type: attribute
    entity: sensor.liquipedia_cs_vitality_last_match
    attribute: score
    name: Score
  - type: attribute
    entity: sensor.liquipedia_cs_vitality_last_match
    attribute: event
    name: Tournoi
  - entity: button.liquipedia_cs_update_all
```

## Notes

- L'intégration met à jour les données toutes les heures par défaut
- Les données sont mises en cache pour limiter les requêtes vers Liquipedia
- Le bouton permet de forcer une mise à jour sans attendre l'intervalle normal

## Prérequis

Cette intégration requiert :
- Home Assistant 2023.2 ou supérieur
- Python 3.9 ou supérieur
- Les dépendances `lxml` et `requests` (installées automatiquement)