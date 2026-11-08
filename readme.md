# Island Patcher (non officiel)

Outil Python pour appliquer deux patches binaires et/ou une traduction française hors ligne à Island 1.2.9 (Windows x64).

## Avertissement / Disclaimer

**English**  
This project is provided for educational and research purposes only. Use it at your own risk. The author(s) are not responsible for any direct or indirect damage, data loss, system failure, or account restrictions resulting from the use of this software.

**Français**  
Ce projet est fourni à des fins éducatives et de recherche uniquement. Vous l’utilisez à vos propres risques. L’auteur (ou les auteurs) n’est pas responsable de tout dommage direct ou indirect, perte de données, dysfonctionnement du système, ou restriction de compte résultant de l’utilisation de ce logiciel.

## Compatibilité

- Testé **uniquement** sur une compilation d’Island 1.2.9 pour Windows x64.
- La compatibilité avec les prochaines versions **n’est pas garantie**, ni avec toutes les compilations portant le même numéro de version.
- Le script vérifie les octets attendus avant toute modification et s’arrête en cas de différence. Ces vérifications ne garantissent pas à elles seules le bon fonctionnement de l’application.

## Installation

```bash
pip install -r requirements.txt
```

## Utilisation

### Patch uniquement

```bash
python island_tool.py patch island.exe
```

Crée `island_patched.exe`.

### Patch + traduction française

```bash
python island_tool.py all-in-one island.exe
```

Crée `island_FR.exe` (patch + traduction française depuis `traductions_fr.json`).

### Options

- `-o sortie.exe` : chemin de sortie personnalisé.
- `--compact-fr` : remplace aussi les textes russes par le français pour gagner de la place.

## Activation après le patch

Après avoir lancé la version patchée d’Island :

1. Ouvre **Island Pro** dans l’application.
2. Dans le champ prévu à cet effet, saisis une clé au format `ISL1-...`.
3. Valide pour activer la fonctionnalité.

**Note :** cette étape concerne uniquement l’activation locale de la fonctionnalité dans l’interface. Aucune clé n’est fournie avec ce projet.

## Fichiers nécessaires

- `island_tool.py` : script principal.
- `traductions_fr.json` : dictionnaire de traductions (791 entrées).
- `requirements.txt` : dépendances.

## Notes

- L’original n’est jamais modifié : une copie est créée.
- Aucun appel réseau : tout se fait localement.
- Les textes dynamiques et les messages natifs ne sont pas tous couverts.
- Ce projet n’est affilié ni aux développeurs d’Island, ni à toute autre entité tierce.