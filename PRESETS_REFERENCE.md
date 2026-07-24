# Memoire geometrique -- definitions des presets

Reference pour chaque objet de la liste "Presets" de VanovaTikZSketch :
definition mathematique precise + usage typique en geometrie/topologie.
Consultable hors de l'appli, ou via l'infobulle (survol) et la rangee
"Definition" sous le menu deroulant Presets.

## Formes euclidiennes de base

**Perfect circle**

Cercle euclidien standard. Sert de base pour tout disque, boule 2D, ou point epaissi dans un diagramme.

**Perfect ellipse**

Ellipse standard -- utilisee comme base perspective d'un disque/cercle vu en 3D (ex. base d'un cylindre, section d'une surface de revolution).

**Square**

Carre -- cellule de base d'un pavage, ou fondamental domain carre (ex. le carre [0,1]^2 dont on identifie les bords pour obtenir un tore).

**Perfect rectangle**

Rectangle -- domaine fondamental generique, boite englobante, ou support d'un graphique/axe.

**Equilateral triangle**

Triangle equilateral -- simplexe standard en dimension 2 (2-simplexe), brique de base d'une triangulation/complexe simplicial.

**Regular pentagon**

Pentagone regulier -- polygone fondamental pour certaines surfaces hyperboliques compactes (pavages du plan hyperbolique).

**Regular hexagon**

Hexagone regulier -- cellule du pavage hexagonal du plan, domaine fondamental du reseau triangulaire/tore hexagonal.

**5-point star**

Etoile a 5 branches -- marqueur decoratif ou point remarquable (ex. singularite, point critique) a mettre en evidence.

**Rhombus / diamond**

Losange -- parallelogramme a cotes egaux ; cellule d'un reseau rhombique, ou domaine fondamental d'un tore oblique.

**Trapezoid**

Trapeze -- utilise pour des projections/perspectives, ou comme domaine fondamental d'un feuilletage lineaire par morceaux.

**Parallelogram**

Parallelogramme -- domaine fondamental typique d'un reseau Z^2 dans R^2 (le tore T^2 = R^2/Z^2 se represente ainsi).

**Circular sector (pie slice)**

Secteur circulaire (part de tarte) -- portion d'angle donne d'un disque ; utile pour illustrer un angle, une carte en coordonnees polaires, ou une orbifold conique.

**Annulus (ring)**

Anneau (deux cercles concentriques) -- exemple standard de surface de genre 0 a deux bords ; domaine fondamental d'un cylindre plat S^1 x [0,1].

**Cross / plus mark**

Croix -- repere/marqueur de point, ou symbole de transversalite entre deux courbes.

**Double-headed arrow**

Fleche double -- notation pour une bijection ou un isomorphisme reciproque (A <-> B), ou pour indiquer une distance/mesure entre deux points.

**Right-angle mark**

Marque d'angle droit -- symbole standard pour indiquer l'orthogonalite entre deux segments/courbes dans une figure geometrique.

## Topologie / lieux de degenerescence

**Lens / eye mark (Dj style)**

Marque en 'lentille' (vesica) -- symbole utilise pour marquer un point de degenerescence D1 sur le lieu singulier D d'une structure de Poisson log-symplectique (classification a la Radko d'un feuilletage symplectique sur une surface orientable).

**Handle (with hatch marks)**

Anse (handle) -- brique de base de la decomposition en anses d'une surface : coller une anse a une sphere fait monter le genre de 1 (utilise pour construire un tore, un genre-2, etc.).

**Torus (meridian + longitude)**

Tore (meridien + longitude) -- surface de genre 1, T^2 = S^1 x S^1. Les deux cercles dessines sont les generateurs standards \alpha (meridien) et \beta (longitude) de \pi_1(T^2) = Z^2.

**Genus-2 surface (sketch)**

Surface de genre 2 (bretzel a deux anses) -- exemple canonique de surface fermee orientable avec \chi = -2 ; utilisee pour illustrer la classification des surfaces ou un espace de modules M_2.

**Cusp / fold singularity mark**

Marque de point de rebroussement (cusp/fold) -- symbole pour un point singulier ou deux branches d'une courbe se rencontrent tangentiellement (singularite de type cusp dans la theorie des singularites/catastrophes).

**Mobius strip (sketch)**

Ruban de Mobius (schema) -- surface non-orientable a un bord et un seul cote, obtenue par un demi-tour dans l'identification d'un rectangle. Exemple de base de fibre non trivial (fibre en droites sur S^1).

**Klein bottle (sketch)**

Bouteille de Klein (schema) -- surface fermee non orientable sans bord ; ne se plonge pas dans R^3 sans auto-intersection (le croisement dessine est une convention de projection 2D, la vraie construction demande la dimension 4).

## Cartes / atlas (varietes)

**Chart map (manifold, U, phi, tilde U)**

Carte locale (chart) -- ouvert U d'une variete M envoye par un homeomorphisme \varphi sur un ouvert \widetilde U de R^n : la brique de base de la definition d'une variete differentiable.

**Atlas: two charts + transition map**

Atlas a deux cartes -- deux ouverts U_1, U_2 qui se recouvrent, avec leurs cartes \varphi_1, \varphi_2 et l'application de changement de cartes (transition map) \varphi_{12} = \varphi_2 \circ \varphi_1^{-1}, qui doit etre un diffeomorphisme pour que l'atlas soit lisse.

## Geometrie differentielle

**Tangent vector T_pM at a point**

Vecteur tangent T_pM en un point p -- element de l'espace tangent, represente comme une fleche le long de la direction de deplacement infinitesimal d'une courbe passant par p.

**Normal vector at a point**

Vecteur normal en un point -- vecteur orthogonal au plan/espace tangent en p, utilise pour orienter une hypersurface ou definir une courbure normale.

**Vector field along a curve**

Champ de vecteurs le long d'une courbe -- assignation lisse d'un vecteur tangent en chaque point ; utilise pour illustrer un flot, une equation differentielle, ou une section d'un fibre tangent.

**Fiber bundle (E, pi, B, fiber F)**

Fibre (fiber bundle) -- espace total E, base B, projection \pi : E -> B, et fibre type F = \pi^{-1}(b). Structure centrale de la geometrie differentielle (fibre vectoriel, fibre principal, etc.).

**Lie groupoid (G rightrightarrows M)**

Groupoide de Lie G \rightrightarrows M -- deux varietes G (fleches/morphismes) et M (objets/unites) reliees par des submersions source s et but t, avec une multiplication partielle ; generalise a la fois un groupe de Lie (M = point) et une variete (G = M). Central en geometrie de Poisson (groupoides symplectiques).

**Commutative diagram (square)**

Diagramme commutatif (carre) -- quatre objets A, B, C, D et quatre morphismes f, g, h, k tels que h \circ f = k \circ g, i.e. les deux chemins A -> D coincident. Notation standard en algebre/theorie des categories (style Quiver).

**Foliation / symplectic leaves**

Feuilletage / feuilles symplectiques -- une variete de Poisson se decompose canoniquement en une union disjointe de sous-varietes symplectiques immergees, ses feuilles symplectiques (theoreme de decomposition de Weinstein) ; un feuilletage symplectique regulier correspond exactement a une structure de Poisson reguliere.
