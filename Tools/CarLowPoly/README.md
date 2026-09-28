# CarLowPoly – pipeline, który zrobił `Assets/Models/BMW_M4_LowPoly`

Działa bez GUI Blendera: `pip install bpy triangle scipy` (Blender 5.0 jako moduł Pythona 3.11) + numpy.
Oryginalnego `bullet.dff` nie ma w repo – połóż go obok skryptów.

```bash
python3 prep.py                                   # -> prep.blend (+ kidney_right.npy)
python3 parts.py -- retopo partsR.blend           # retopologia per panel (aktualna wersja)
python3 export.py -- partsR.blend out main        # -> out/BMW_M4_LowPoly.fbx + .blend (SMOOTH_ANGLE=30 domyślnie, 0 = płaskie)
python3 export.py -- partsR.blend out main dbg && python3 holes.py -- out/debug_main.blend chk   # test dziur jak w Unity
python3 review.py -- out/debug_main.blend rev/s                     # 30 zbliżeń kontrolnych
# starsze warianty: parts.py -- keep (B, zostają oryginalne wierzchołki) / -- move (A, quadric collapse)
```

Kroki:
1. **prep.py** – czyta DFF (`dff.py`), bierze tylko części zewnętrzne (bez interioru, silnika, zawieszenia),
   przypisuje materiały po teksturach, zgrzewa wierzchołki, usuwa drobne detale (<3.5 cm) i wycina gęste nerki grilla.
   Potem **test widoczności**: z każdej ściany puszcza promienie (z góry i z boku, nie od spodu); ściany,
   których nie widać z zewnątrz (koła, ziemia, bryły zastępcze silnika/bagażnika zasłaniają), są usuwane.
2. **parts.py** + **retopo.py** – każda część osobno, prawa połowa auta (lewa = lustro):
   - linie cech: krawędzie otwarte, granice materiałów, zagięcia > 20° (łapie też zawinięte krawędzie paneli), szew x=0;
   - linie dzielone na łańcuchy między narożnikami i upraszczane (Douglas-Peucker na oryginalnych wierzchołkach)
     z tolerancją zależną od odległości do sąsiedniej linii (wąskie paski: listwy, ramki szyb) – brzegi się nie krzyżują;
     brzegi powstałe tylko przez wycięcie ukrytych ścian (zygzak pod nakładającą się warstwą) upraszczane mocniej;
     sąsiednie regiony dzielą te same punkty → brak szczelin;
   - każdy region rozkładany płasko (LSCM) i wypełniany od nowa jakościową triangulacją Delaunay (Triangle),
     zagęszczaną tylko tam, gdzie odbiega od oryginału o więcej niż `RETOPO_TOL`, z limitem wierzchołków na region;
   - regiony, których nie da się rozłożyć, idą przez ostrożną redukcję (`decim.py`) z tym samym obrysem;
   - nerki grilla odbudowywane z obrysu oryginału (`kidney.py`), koło budowane proceduralnie (`wheel.py`).
3. **post.py** – test widoczności na gotowej siatce (odwraca/usuwa ściany, cienkie kołnierze oznacza jako dwustronne),
   dokłada płytę podłogi, czarną ścianę za grillem i osłonę wcięcia w szybie.
4. **export.py** – skleja karoserię, ustawia koła (pivot w środku), skaluje do 4.671 m, obraca pod Unity;
   cieniowanie: gładko w panelu, ostro na krawędziach > `SMOOTH_ANGLE` (30°) i granicach materiałów, liczone na siatce
   bez dwustronnych kopii (kopie dostają odwrócone normalne oryginałów). `normals.py` (przeniesienie normalnych
   z gęstego oryginału, `NORMALS_FROM=prep.blend`) zostało jako opcja – dawało fałdy przy szczelinach paneli.
