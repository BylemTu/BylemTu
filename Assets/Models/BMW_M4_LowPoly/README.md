# BMW M4 (F82) – low-poly, bez interioru

Zrobione z modelu GTA SA (`bullet.dff`, BMW M4 F82 2018 by f10cu), każda część osobno
(karoseria, drzwi, maska, klapa, zderzaki, błotniki, progi, szyby, lampy, grill, koła).

| | |
|---|---|
| Karoseria | ~6.9k wierzchołków (Blender) |
| Koło (każde) | 436 wierzchołków (28 segmentów) |
| Plik | `BMW_M4_LowPoly.fbx` |

Podgląd: `Preview/` (`BMW_*` = render, `wire_*` = z siatką).
Plik do edycji w Blenderze: `Source/BMW_M4_LowPoly/BMW_M4_LowPoly.blend` (poza `Assets/`, żeby Unity go nie importowało).
Starsze wersje A/B (redukcja wierzchołków, płaskie cieniowanie): `Source/BMW_M4_LowPoly/old/`.

## Jak to zrobione
1. **Retopologia per panel**: każda część jest dzielona wzdłuż swoich prawdziwych linii (łączenia paneli,
   zagięcia, zawinięcia krawędzi, granice lakier/szyba/światło), te linie są upraszczane do oryginalnych
   wierzchołków, a każdy panel wypełniany od nowa równymi trójkątami (bez długich „drzazg” i wachlarzy).
2. **Cieniowanie z oryginału**: normalne są przeniesione z gęstego modelu, więc światło układa się jak na
   prawdziwym aucie – ostre krawędzie tylko tam, gdzie auto naprawdę je ma (zagięcia, łączenia paneli,
   obrysy szyb, świateł i nadkoli), gładko wewnątrz panelu.

## Co jest w środku
- `Body` – jedna siatka, materiały: `Paint`, `Glass`, `Black`, `Chrome`, `Headlight`, `Taillight`
  (lakier to osobny materiał → kolor auta zmieniasz jednym materiałem w Unity).
- `Wheel_FL`, `Wheel_FR`, `Wheel_RL`, `Wheel_RR` – osobne obiekty, **pivot w środku koła**, oś obrotu = lokalne X
  (lewe koła są lustrzane w danych siatki, więc obrót z `WheelCollider.GetWorldPose` działa bez dodatkowych rotacji).
  Materiały: `Tire`, `Rim`, `Brake`, `Caliper`.
- Brak interioru (kabina zamknięta przyciemnianymi szybami), brak silnika; spód zamknięty płaską czarną płytą.

## Import do Unity
- **Import Settings → Model → Normals: `Import`** (ważne! `Calculate` wyrzuci przeniesione normalne
  i auto znowu będzie wyglądać na pogięte).
- Skala 1:1 (metry): długość 4.67 m, rozstaw osi 2.81 m – wymiary prawdziwego M4 F82.
- Oś Y = góra, przód auta = +Z, pivot root-a na ziemi w połowie rozstawu osi. Root nie ma rotacji -90°.
- Środki kół (lokalnie względem root-a): przód z = +1.40, tył z = −1.40, x = ±0.78, y = 0.32; promień koła 0.32 m.

## Uwaga o prawach
Kształt pochodzi z moda z gtaall.com (autor: f10cu), który sam najpewniej bazuje na modelu z innej gry.
Do prywatnego testu – OK; do publicznego/komercyjnego projektu lepiej mieć własny model.

## Skrypty
`Tools/CarLowPoly/` – patrz tamtejszy README. Gęstość: `RETOPO_TOL` (parts.py, domyślnie 0.016)
i `fill` w `retopo.py` (0.045); segmenty koła: `S` w `wheel.py`.
