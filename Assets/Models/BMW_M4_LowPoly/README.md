# BMW M4 (F82) – low-poly, bez interioru

Dwie wersje tego samego auta zrobione z modelu GTA SA (`bullet.dff`, BMW M4 F82 2018 by f10cu).
Każda część auta była obrabiana osobno (karoseria, drzwi, maska, klapa, zderzaki, błotniki,
progi, szyby, lampy, grill, koła) – nie jednym narzędziem na całe auto.

| | A – `A_Moja/` | B – `B_Twoja/` |
|---|---|---|
| Metoda | redukcja krawędzi z **przesuwaniem** wierzchołków w optymalne miejsce (quadric error) | **oznaczam istotne wierzchołki, resztę usuwam** – każdy wierzchołek, który został, to oryginalny wierzchołek z modelu |
| Karoseria (Blender) | ~5.6k wierzchołków | ~5.6k wierzchołków |
| Koło (każde) | 436 wierzchołków (28 segmentów) | 436 wierzchołków (28 segmentów) |

Pliki do edycji w Blenderze: `Source/BMW_M4_LowPoly/*.blend` (poza `Assets/`, żeby Unity ich nie importowało).
Podgląd: `Preview/` (`*_front`, `*_rear`, `*_side`, `wire_*` = z siatką).

## Co jest w środku
- `Body` – jedna siatka, materiały: `Paint`, `Glass`, `Black`, `Chrome`, `Headlight`, `Taillight`
  (lakier to osobny materiał → kolor auta zmieniasz jednym materiałem w Unity).
- `Wheel_FL`, `Wheel_FR`, `Wheel_RL`, `Wheel_RR` – osobne obiekty, **pivot w środku koła**, oś obrotu = lokalne X
  (lewe koła są lustrzane w danych siatki, więc obrót z `WheelCollider.GetWorldPose` działa bez dodatkowych rotacji).
  Materiały: `Tire`, `Rim`, `Brake`, `Caliper`.
- Brak interioru (kabina zamknięta przyciemnianymi szybami), brak silnika; spód zamknięty płaską czarną płytą.
- Cieniowanie płaskie (każda krawędź ostra, bez smooth).

## Import do Unity
- Skala 1:1 (metry): długość 4.67 m, rozstaw osi 2.81 m – wymiary prawdziwego M4 F82.
- Oś Y = góra, przód auta = +Z, pivot root-a na ziemi w połowie rozstawu osi. Root nie ma rotacji -90°.
- W Import Settings zostaw **Normals: Import** (płaskie normalne są zapisane w pliku). Jeśli wolisz,
  `Normals: Calculate` + `Smoothing Angle: 0` daje to samo.
- Środki kół (lokalnie względem root-a): przód z = +1.40, tył z = −1.40, x = ±0.78, y = 0.32; promień koła 0.32 m.

## Liczba wierzchołków w Unity
Blender liczy ~5.6k wierzchołków karoserii. Unity przy płaskim cieniowaniu rozdziela wierzchołki
na każdą ścianę (każdy trójkąt dostaje własne normalne), więc Statystyki w Unity pokażą więcej
(~3 × liczba trójkątów). To normalne dla stylu „flat low-poly” i nadal jest bardzo lekko.

## Uwaga o prawach
Kształt pochodzi z moda z gtaall.com (autor: f10cu), który sam najpewniej bazuje na modelu z innej gry.
Do prywatnego testu – OK; do publicznego/komercyjnego projektu lepiej mieć własny model.

Skrypty, którymi to zrobiono: `Tools/CarLowPoly/`.

## Poziom detalu
W `Tools/CarLowPoly/parts.py` jest `DETAIL` (teraz 1.4). Mnoży budżet wierzchołków każdej części:
1.0 = pierwsza, bardziej low-poly wersja (~4.3k), 1.4 = obecna (~5.6k). Segmenty koła: `S` w `wheel.py`.
