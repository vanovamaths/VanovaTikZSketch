# VanovaTikZSketch (v4.16)

*(anciennement GeoSketch2TikZ)*

## Version web (nouveau)

En plus de l'appli de bureau (PyQt5, `python3 main.py`), il existe maintenant une **version web autonome** dans le dossier `docs/` -- HTML/CSS/JS pur, aucune installation, tourne entierement dans le navigateur (rien n'est envoye a un serveur). C'est une reimplementation independante (memes algos : lissage anti-tremblement + ajustement de courbes de Bezier de Schneider + export TikZ), pas encore toutes les fonctionnalites de la version bureau (pas d'import photo, pas de presets pour l'instant), mais l'essentiel du dessin -> TikZ y est.

**Pour la publier sur GitHub Pages** (gratuit, URL du style `https://<ton-pseudo>.github.io/VanovaTikZSketch/`) :
1. Cree le depot sur GitHub et pousse ce dossier dedans (voir plus bas).
2. Dans le depot GitHub : Settings -> Pages -> Source : "Deploy from a branch" -> Branch : `main`, dossier `/docs` -> Save.
3. Au bout d'une minute ou deux, le site est en ligne a l'URL indiquee sur la meme page.

**Pour tester en local avant de publier**, depuis `docs/` :
```
python3 -m http.server 8000
```
puis ouvrir `http://localhost:8000` dans un navigateur (ouvrir `index.html` directement au double-clic marche aussi, mais un petit serveur local evite certains soucis de securite navigateur).

**Pour publier tout le depot sur GitHub** (depuis ce dossier, dans le Terminal) :
```
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<ton-pseudo>/VanovaTikZSketch.git
git push -u origin main
```
(cree d'abord le depot vide sur github.com avant le `git remote add`). Pense a ajouter une licence (MIT par exemple) si tu veux clarifier ce que les autres ont le droit de faire avec le code -- dis-le-moi si tu veux que je t'en ajoute une.

## v4.16 — extraction "design vide" + seuillage adaptatif

Deux changements, pour repondre au vrai besoin : importer N'IMPORTE QUELLE photo/schema et recuperer des formes vides (juste le contour, aucune couleur/remplissage/interpretation), a modifier soi-meme ensuite.

- **Extraction volontairement "vide"** : le bouton "Import photo" / "Photo URL" -> "Extract the design" n'essaie plus de deviner les couleurs, les zones grisees/remplies, ni aucun symbole -- il trace uniquement le squelette noir du dessin en formes vectorielles simples (`BezierStroke`, sans fill), directement editables avec Select comme n'importe quel trait dessine a la main.
- **Seuillage adaptatif (local) au lieu d'Otsu global** : un seul seuil global casse des que l'eclairage de la photo n'est pas parfaitement uniforme (ombre, vignettage, reflet) -- exactement le genre de photo prise avec un telephone. Chaque pixel est maintenant compare a la moyenne de son voisinage local plutot qu'a un seuil unique pour toute l'image, ce qui suit les variations lentes d'eclairage tout en gardant les traits fins qui sont reellement plus sombres que leur entourage immediat.
- **Hachures/pointilles retires au lieu de donner un "splat"** : un amas de traits qui se croisent (hachures, un tiret de courbe pointillee) donne un contour exterieur genuinement herisse une fois trace comme un blob -- ce n'est pas un defaut de lissage, c'est la vraie forme de l'union de plusieurs traits fins qui se croisent. Un premier essai de reconstruction automatique (squelette + repassage en traits ouverts) a ete tente puis abandonne : sur un vrai dessin a main levee le squelette se fragmente en dizaines de petits bouts, ce qui est pire que le blob de depart. Choix final, plus simple et plus fiable : ces petits amas (detectes par taille ET par "compacite" -- perimetre enorme pour une aire quasi nulle) sont retires proprement de l'extraction plutot que de laisser un artefact. Les grandes silhouettes du dessin restent intactes ; les hachures/pointilles sont a refaire a la main (rapide avec l'outil stylo + Auto-finish).


# VanovaTikZSketch (v4.15)

## Correctif v4.15 — formes extraites avec une boite englobante delirante (loin hors du dessin)

Bug plus profond trouve pendant le travail sur le nettoyage automatique post-extraction : certaines formes fermees (typiquement un contour proche d'un cercle, dense, comme le contour exterieur d'un rond hachure) ressortaient de l'extraction avec une boite englobante totalement absurde -- des centaines de pixels hors du cadre du dessin -- et etaient parfois classees "remplies" a tort.

Cause reelle (dans `curvefit.py`, l'ajustement de courbes de Bezier a la Schneider) : pour une forme FERMEE, le tout premier point et le tout dernier point du contour sont le meme point (la boucle se referme), alors que l'arc entre eux fait le tour complet de la forme. L'algorithme essayait quand meme d'ajuster tout le contour en UNE seule courbe de depart avec ces deux points quasi-identiques comme extremites : la corde (distance a vol d'oiseau) entre eux est ~0, ce qui rend le systeme lineaire qui calcule la position des points de controle numeriquement instable -- il pouvait renvoyer des points de controle a des centaines de pixels du dessin.

Corrige :
- Les contours fermes sont maintenant pre-decoupes en plusieurs arcs ouverts avant l'ajustement (au lieu d'un seul ajustement degenere sur toute la boucle) -- chaque morceau a une vraie corde non nulle, donc le calcul reste stable.
- Garde-fou supplementaire : la magnitude des points de controle est desormais bornee par la taille reelle du nuage de points (au lieu de la distance corde-a-corde qui peut s'effondrer a 0), donc meme un cas limite ne peut plus s'echapper loin du dessin.
- Filet de securite final : si l'ajustement Bezier echoue quand meme sa verification de coherence (a une tolerance plus large en dernier recours), la forme est reconstruite comme une simple polyligne suivant fidelement les points traces, garantissant une boite englobante toujours correcte plutot qu'une forme aberrante.

Verifie avec un test synthetique (anneau + zone hachuree en decalage + poussiere isolee) : les 3 formes extraites ont maintenant des boites englobantes coherentes avec le dessin source, alors qu'avant le correctif 2 des 3 formes debordaient de plus de 100 px hors cadre et etaient mal classees "remplies".

**Nouveau preset** : `genus2_curves_tau_sigma` -- la surface de genre 2 (somme connexe de deux tores) du schema que tu essayais d'importer par photo, prete a inserer directement depuis le menu Presets, avec ses courbes standards annotees $\tau_1$, $\tau_2$ (meridiens de chaque anse), $\sigma$ (courbe separante au cou de la somme connexe) et $\tau$ (courbe non separante traversant les deux anses) -- plus besoin de repasser par l'extraction photo pour ce schema-la.


## Correctif v4.14 — plus de "splat" gris sur les zones grisees/hachurees

Meme apres le fix v4.13, une zone grisee/hachuree a la main (l'ombrage typique d'un "trou"/genre dans un dessin de topologie fait main) donnait encore une tache grise en forme d'etoile/eclat au lieu d'une forme propre : le contour trace suit chaque trait de hachure individuellement, ce qui donne un contour tres dentele.

Corrige :
- Les petits espaces ENTRE les traits de hachure sont maintenant combles (fermeture morphologique) avant le tracé, pour que toute la zone grisee/hachuree ressorte comme UN SEUL contour propre au lieu de dizaines de fragments en dents de scie.
- Ce contour recoit en plus un lissage + fairing de courbure nettement plus fort (specifique aux zones remplies, les contours d'encre/traits restent legers) pour eliminer les dernieres pointes.
- Echantillonnage de la couleur interieure rendu plus robuste (plusieurs rayons, moyenne plutot qu'un seul pixel), donc une zone partiellement hachuree ressort dans le bon ton de gris au lieu d'etre ratee.


## Correctif v4.13 — extraction de photo fidele au design original

Le decoupage en 5 niveaux de luminance (v4.9) donnait de bons resultats sur une vraie photo, mais cassait completement un diagramme/schema (fond blanc + traits fins) : les bandes sont decoupees par QUANTILE de pixels, ce qui tranche au hasard a travers le degrade d'anticrenelage d'un trait fin et fragmente les lignes en morceaux qui se croisent (les formes en "noeud papillon" que tu as vues).

Corrige :
- L'extraction detecte maintenant automatiquement si l'image est un **diagramme/trait** (fond plat + traits fins -- le cas normal de cette appli) ou une **vraie photo** (tons continus), et choisit la bonne strategie.
- Pour un diagramme : deux bandes FIXES (encre quasi-noire = traits/contours, gris moyen = zones grisees/remplies) au lieu de 5 bandes par quantile -- reproduit fidelement le design original (contours + remplissages) sans fragmentation.
- Une forme n'est remplie que si son INTERIEUR (echantillonne en plusieurs points robustes, pas un seul pixel) est reellement grise/coloree -- le contour exterieur d'un dessin reste un simple contour au lieu de devenir un gros blob opaque.
- La strategie multi-niveaux (photo) reste utilisee automatiquement pour une vraie photo.


## Nouveau dans la v4.12 — plus de 3D, tetes de fleche Quiver, fenetres multiples

- **3D entierement retire** : plus de bouton "Revolve to 3D", plus de case "Auto 3D preview", plus de panneau "3D TikZ code" ni de boutons d'export 3D. Le panneau "Live preview" est redevenu un aperçu 2D simple. Ca libere aussi pas mal d'espace dans l'interface.
- **Tetes de fleche style Quiver** : le panneau flottant qui apparait quand tu selectionnes une Fleche a maintenant une rangee **Head** avec 4 styles -- Stealth (plein, par defaut), Classical (V ouvert simple), Harpoon (une seule barbe), None (pas de tete, se lit comme une simple ligne). Exporte en TikZ reel (`-{Stealth}`, `->`, `-{Harpoon}`, `-`).
- **❐ New window** confirme/visible en rangee 1 (Tools) -- ouvre une fenetre vierge independante pour travailler sur un autre projet en parallele (raccourci Ctrl+Shift+N), distincte de "Duplicate to new window" qui copie le dessin actuel.
- Toolbar re-verifiee : aucun bouton caché derriere une fleche de debordement.


## Correctif v4.11 — crash tablette ("Too many nested CFRunLoopRuns")

Cause trouvee : avec l'outil **Text/LaTeX** actif, un simple appui du stylet ouvrait directement la boite de dialogue (modale) pour taper le LaTeX. Sur certains Mac/tablettes, macOS continue d'envoyer des evenements de stylet au canvas MEME PENDANT que cette boite modale est ouverte -- si un de ces evenements etait (re)interprete comme un nouvel appui, une DEUXIEME boite s'ouvrait par-dessus, puis une troisieme, etc., jusqu'a des centaines de boites imbriquees et un crash de l'app ("Too many nested CFRunLoopRuns").

Corrige : le canvas ignore desormais tout evenement de stylet/souris tant qu'une boite de dialogue modale est deja ouverte (Photo URL, couleur, ouvrir/enregistrer, le label LaTeX...). Plus de boites en cascade possible.


## Nouveau dans la v4.10 — moins de boutons, plus d'automatique

- **Idealize** et **★ Machine finish (all)** ne sont plus des boutons a cliquer : le nettoyage (jitter enleve, courbure lissee) est desormais applique automatiquement a chaque trait, sans rien demander.
- **Smooth finish** n'est plus une case a cocher : c'est desormais toujours actif.
- **❐ New window** (rangee Tools, raccourci Ctrl+Shift+N) : ouvre une seconde fenetre completement VIERGE (contrairement a "Duplicate to new window" qui copie le dessin actuel).


## Nouveau dans la v4.9 — extraction photo fidele + auto-finish qui ne deforme plus

- **Auto-finish ne change plus le dessin** : avant, tout contour ferme dessine normalement etait automatiquement pousse vers une symetrie bilaterale (`symmetrize_closed_curve`), ce qui deformait le design meme quand ce n'etait pas demande. Corrige : l'auto-finish ne fait plus QUE corriger le trait (jitter du poignet enleve, courbure lissee) -- il ne force plus une forme differente de celle dessinee. La symetrisation complete reste disponible, mais uniquement via une action volontaire (Idealize / ★ Machine finish).
- **Extraction de photo beaucoup plus fidele** : l'extraction ne produit plus un simple contour noir qui ne ressemble pas a l'original.
  - Les couleurs REELLES de la photo sont maintenant echantillonnees et appliquees a chaque forme extraite (au lieu d'un noir uniforme).
  - L'image est desormais decoupee en 5 niveaux de luminance (posterisation) au lieu d'un seul masque noir/blanc -- plus de regions/details distincts sont captures.
  - Resolution d'analyse augmentee (900px au lieu de 640), lissage allege (le contour colle davantage au vrai contour au lieu d'etre arrondi comme un trait dessine a la main).


## Nouveau dans la v4.8 — memoire geometrique avancee (definitions des presets)

- Chaque preset de la liste deroulante a maintenant une **definition mathematique precise + son usage typique** (verifiees par recherche : Lie groupoid, foliation/feuilles symplectiques, degeneracy locus a la Radko, etc.).
- **Infobulle** : survole n'importe quel nom dans le menu "Presets" pour voir sa definition.
- **Rangee "Definition"** (sa propre rangee d'outils, jamais cachee) : affiche en direct la definition complete du preset actuellement selectionne dans le menu deroulant.
- **`PRESETS_REFERENCE.md`** : fichier a part listant les 32 presets avec leur definition, consultable hors de l'appli.
- Fenetre agrandie (1780x1200, min 1180x960) pour que les 7 rangees d'outils restent toutes visibles sans jamais se chevaucher.


## Nouveau dans la v4.7 — copier/coller, ordre, transformations, fenetres

- **Copy / Paste / Duplicate** d'une forme selectionnee (Ctrl/Cmd+C, +V, +D) -- outils standards des logiciels vectoriels (Graphic, Paint S...) qui manquaient.
- **Ordre (z-order)** : Bring to front / Forward / Backward / Send to back.
- **Transform** : Flip H, Flip V, Rotate 90 deg autour du centre de la forme.
- **⧉ Duplicate to new window** : ouvre une SECONDE fenetre independante avec une copie du dessin entier -- pour travailler sur une variante du meme design en parallele sans toucher a l'original.
- Nouvelle rangee d'outils "Arrange" (barre du haut).


## Nouveau dans la v4.5 — tirets/pointilles parfaitement reguliers

- **Correction du bug source** : une courbe main levee (pression variable) marquee "dashed"/"dotted" est desormais TOUJOURS tracee comme UN SEUL chemin continu a epaisseur constante (a l'ecran ET dans le TikZ exporte). Avant, chaque segment de Bezier redemarrait son propre motif de tirets, donnant des tirets de tailles/espacements incoherents (le probleme signale sur le trait pointille de la "taille" du tore). Desormais, meme distance, meme taille, automatiquement.
- **Style Solid/Dashed/Dotted disponible sur N'IMPORTE QUELLE forme** (avant : seulement Ligne/Fleche) -- selectionne un contour main levee, un cercle, un polygone, et choisis son style dans le panneau flottant "Style"/"Edge".
- Ellipse supporte enfin le style dashed/dotted (avant : uniquement trait plein).


## Nouveau dans la v4.4 — controles de fleches style Quiver + navigation

- **Panneau "Edge" flottant** : selectionne une Ligne/Fleche (outil Select), un panneau apparait en haut a droite du canvas -- **Curve** (glisseur pour courber l'arete en arc, exactement comme le controle Curve de Quiver), **Reverse** (inverse le sens), **style** Solid/Dashed/Dotted, **Double line** (deux traits paralleles, pour un monomorphisme par exemple). Tout s'applique en direct et s'exporte en TikZ reel (courbe Bezier exacte, pointilles, trait double).
- **Navigation rapide et fluide** (3e rangee d'outils) : molette = zoom (centre sur le curseur), Espace+glisser ou clic-milieu+glisser = pan, boutons Zoom -/+, 100%, "Fit to drawing". Raccourcis clavier : +/- pour zoomer, 0 pour reinitialiser.
- La gomme, l'idealisation et l'export suivent desormais la VRAIE courbe d'une fleche courbee (pas la corde droite).


## Nouveau dans la v4.3 — labels 100% clavier, style Quiver

- Les lettres/symboles ne se dessinent plus au stylo. Outil **Text / LaTeX** (clic sur le canvas) ou **Name (L)** (forme selectionnee) : une boite de dialogue s'ouvre, tu tapes du vrai LaTeX au clavier -- `\varphi`, `\Sigma_g`, `f_1`, `x^2`, `\to`, `\circ`... -- exactement la philosophie de Quiver (les diagrammes commutatifs).
- Le symbole s'affiche en Unicode reel sur le canvas (`\varphi` -> φ, `\to` -> →, indices/exposants rendus en petits caracteres) via `latex_render.py`. Le texte STOCKE et EXPORTE reste le vrai code LaTeX -- rien ne change pour la compilation `.tex`.
- Nommer une Ligne/Fleche (un morphisme) place desormais le label centre juste au-dessus du segment, comme le label d'une fleche dans un diagramme commutatif -- coherent quel que soit l'ordre dans lequel tu as trace la fleche.


## Nouveau dans la v4.2 — import de photos

- **Import photo... / Photo URL...** (barre d'outils) : ouvre une image de ton ordinateur ou telechargee directement depuis le web (colle l'URL).
- **Extract the design** : les contours principaux de la photo sont detectes (seuillage d'Otsu + suivi de contours de Moore + ajustement Bezier) et deposes sur le canvas comme des formes vectorielles NORMALES — tu peux les selectionner, deplacer, gommer, recolorer, idealiser ou passer au ★ Machine finish, exactement comme un trait dessine a la main. Le design extrait est donc entierement modifiable pour obtenir le dessin que tu veux.
- **Trace over it** : la photo s'affiche en calque estompe sous le dessin (jamais exportee) pour decalquer par-dessus. Case "Show photo" pour masquer/afficher, "Remove photo" pour retirer.
- Marche pour les dessins contrastes (schema noir sur fond clair ou l'inverse — polarite detectee automatiquement). Une photo complexe/faible contraste marchera mieux en mode calque.

## Nouveau dans la v4.1 — correction design automatique

- **★ Machine finish (all)** : un clic re-idealise TOUT le dessin comme un logiciel de design — presque-cercles -> cercles parfaits, presque-droites -> droites accrochees aux angles standard (multiples de 15 deg), contours organiques -> symetrises + lisses par fairing sans retrecissement, epaisseur uniforme. Ctrl+Z pour annuler.
- Finition automatique par defaut renforcee (symetrisation 0.85, fairing de courbure, tolerance plus fine).


Dessine des figures a la main (souris ou tablette graphique) et genere le code LaTeX/TikZ en direct.

## Nouveau dans la v4

**Tablette graphique beaucoup plus reactive.**

1. *Cache de rendu (backing store)* : les formes deja posees sont rendues une seule fois dans un pixmap a la vraie densite de l'ecran ; chaque image ne redessine plus que le trait en cours. La latence du stylet ne depend plus du nombre de formes sur le canvas.
2. *Repaints partiels (dirty rects)* : pendant le trace, seule la zone autour du dernier segment est repeinte.
3. *Filtrage d'entree* : positions sous-pixel du driver tablette, suppression des micro-mouvements (< 1.2 px), lissage exponentiel de la pression — trait stable, moins de points, moins de CPU.
4. *Deplacement instantane* : la forme selectionnee est exclue du cache et dessinee en overlay, donc la deplacer ne redessine jamais le reste.

**Pression du stylet -> epaisseur variable.** Case "Pen pressure" (activee par defaut). L'epaisseur suit la pression, est conservee dans le fichier projet, rendue a l'ecran, et exportee en TikZ (un `\draw` par segment avec sa propre `line width`, `line cap=round`) et en SVG. Decoche-la pour un trait constant 100% machine. "Idealize" force toujours un trait constant (look machine).

**Rendu haute resolution.**

- HiDPI/Retina actif (`AA_EnableHighDpiScaling` + pixmaps HiDPI) : canvas net sur ecran dense.
- **Export SVG** : vectoriel pur, resolution infinie, editable dans Inkscape/Illustrator.
- **Export PNG a echelle reglable** : 2x a 8x au moment de l'export.
- Fleches avec pointe triangulaire pleine (style Stealth), exportees en TikZ `-{Stealth}` (la lib `arrows.meta` est incluse dans le .tex standalone ; ajoute `\usetikzlibrary{arrows.meta}` a ton preambule si tu colles seulement le body).

**Interface reorganisee.** Deux rangees de barre d'outils (outils/actions en haut, style/options en bas), theme sombre raffine.

**Finition automatique** (inchangee, activee par defaut) : primitives parfaites (ligne, cercle/ellipse, polygone) ou contour organique nettoye + symetrise.

## Installation

```bash
python3 -m pip install -r requirements.txt
python3 main.py
```

## Rappel des outils

| Outil | Usage |
|---|---|
| Stylo | Main levee, pression du stylet supportee. Avec finition auto : forme parfaite ou contour nettoye. |
| Ligne / Fleche | Cliquer-glisser |
| Ellipse / Cercle | Cliquer-glisser depuis le coin |
| Polygone | Cliquer chaque sommet, double-clic pour fermer |
| Plume (Bezier) | clic = ancre, glisser = poignees. Entree = terminer, Echap = annuler |
| Texte / LaTeX | Cliquer, saisir du LaTeX |
| Gomme / Selection | Supprimer partiellement / deplacer une forme |

Remplissage : case "Fill closed shapes" + couleur dediee + palette rapide (Alt+clic = remplissage). Prefomes : menu deroulant puis "Insert preset".

Export : panneau de droite — "Copy code", "Export .tex" (standalone, `pdflatex`), "Export SVG", "Export PNG..." (2x-8x).

## Structure

- `shapes.py` — modele des objets (remplissage + epaisseur variable `widths`)
- `shape_recognition.py` — reconnaissance de primitives parfaites
- `smoothing.py` — nettoyage/lissage des contours non reconnus
- `presets.py` — bibliotheque de gabarits
- `curvefit.py` — lissage Bezier (algorithme de Schneider)
- `canvas.py` — widget de dessin, souris/tablette, cache de rendu, tous les outils
- `render.py` — rendu partage (canvas, preview, exports), epaisseur variable
- `erasing.py` — gomme partielle
- `tikz_export.py` — traduction en code TikZ (largeur variable incluse)
- `main_window.py` — fenetre, theme, barres d'outils, panneau de code, exports
- `main.py` — point d'entree

## Limites connues

- Pas d'image de fond a calquer.
- Les prefomes composites s'inserent comme plusieurs formes independantes.
- Pas d'outil arc de cercle partiel ni de courbes parametriques a partir d'une equation.
- La "finition automatique" reste un algorithme geometrique deterministe (moindres carres + lissage), pas un modele d'IA entraine.
