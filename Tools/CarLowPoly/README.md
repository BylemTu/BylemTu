# CarLowPoly – pipeline, który zrobił `Assets/Models/BMW_M4_LowPoly`

Działa bez GUI Blendera: `pip install bpy` (Blender 5.0 jako moduł Pythona 3.11) + numpy.
Oryginalnego `bullet.dff` nie ma w repo – połóż go obok skryptów.

```bash
python3 prep.py                          # -> prep.blend
python3 parts.py -- keep partsB.blend    # wersja B (zostają oryginalne wierzchołki)
python3 parts.py -- move partsA.blend    # wersja A (wierzchołki przesuwane w optymalne miejsce)
python3 export.py -- partsB.blend outB B # -> outB/BMW_M4_LowPoly_B.fbx + .blend
python3 export.py -- partsB.blend outB B dbg && python3 holes.py -- outB/debug_B.blend chk   # test dziur jak w Unity
```

Kroki:
1. **prep.py** – czyta DFF (`dff.py`), bierze tylko części zewnętrzne (bez interioru, silnika, zawieszenia),
   przypisuje materiały po teksturach, zgrzewa wierzchołki, usuwa drobne detale (<3.5 cm) i wycina gęste nerki grilla.
   Potem **test widoczności**: z każdej ściany puszcza promienie (z góry i z boku, nie od spodu); ściany,
   których nie widać z zewnątrz (koła, ziemia, bryły zastępcze silnika/bagażnika zasłaniają), są usuwane.
   Każda ściana jest odwracana w stronę, z której ją widać.
2. **parts.py** + **decim.py** – każda część osobno, prawa połowa auta (lewa = lustro):
   - cechy chronione: krawędzie otwarte, granice materiałów, zagięcia > 38°, szew symetrii x=0;
   - wierzchołki na narożnikach tych linii są zablokowane, wierzchołki na liniach mogą się tylko po nich przesuwać;
   - reszta usuwana w kolejności najmniejszej zmiany kształtu, ze sprawdzaniem odwracania ścian i topologii;
   - jeśli budżet części nie został osiągnięty, ochrona jest luzowana stopniowo (38° → 50° → 62° → 75°).
   - nerki grilla odbudowywane z obrysu oryginału (`kidney.py`), koło budowane proceduralnie na wymiarach oryginału (`wheel.py`).
3. **post.py** – ostatni test widoczności na gotowej low-poly siatce (odwraca/usuwa ściany, cienkie kołnierze
   oznacza jako dwustronne), dokłada płytę podłogi i czarną ścianę za grillem.
4. **export.py** – skleja karoserię, ustawia koła (pivot w środku), skaluje do 4.671 m, obraca pod Unity, zapisuje FBX.
