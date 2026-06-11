# Exploratory Data Analysis (EDA): Land Use & Zoning GIS Layers

We have successfully downloaded and analyzed the five newly added ArcMap MapServer query URLs. Here is a comprehensive breakdown of what each dataset represents, its features, and the attributes it contains.

---

## 📊 Summary Table of GIS Layers

| Layer Identifier | Service Name | Feature Count | Geometry Types | Primary Use / Description |
| :--- | :--- | :--- | :--- | :--- |
| **`LandUse_MapServer_2`** | Land Use | 33 | 19 Polygon, 14 MultiPolygon | General Land Use designations (Business Parks, Waterfronts, Residential densities). |
| **`Zoning_MapServer_4`** | DA Exception | 4 | 4 Polygon | Specific Development Agreement (DA) exception boundaries. |
| **`Zoning_MapServer_3`** | Gateway Overlay | 9 | 8 Polygon, 1 MultiPolygon | Zoning overlay boundary zones for the Gateway transit/corridor area. |
| **`Zoning_MapServer_0`** | PUD Overlay | 11 | 9 Polygon, 2 MultiPolygon | Boundaries for Planned Unit Development (PUD) overlay regulations. |
| **`Zoning_MapServer_1`** | Zoning | 369 | 262 Polygon, 106 MultiPolygon | The primary City Zoning District boundaries (Agricultural, Residential, Commercial, Mixed Use). |

---

## 🔍 Detailed Layer Breakdowns

### 1. Land Use (`LandUse_MapServer_2`)
This layer represents general land-use policies. It maps larger regional tracts into planning descriptions.
* **Key Attribute**: `LANDUSEDESC` (Land Use Description)
* **Designations Breakdown**:
  * **Business Park**: 6 features
  * **Mixed Waterfront**: 4 features
  * **Institutional**: 3 features
  * **Rural Residential**: 3 features
  * **Planned Community**: 2 features
  * **Low Density Residential**: 2 features
  * **Regional Commercial**: 2 features
  * **Mixed Use Commercial Overlay**: 1 feature
  * **Office Warehouse**: 1 feature
  * **Town Center Overlay**: 1 feature

---

### 2. DA Exception (`Zoning_MapServer_4`)
This layer represents explicit exceptions to standard zoning codes via developer-city Development Agreements (DA). It lists exactly 4 named areas:
1. **Brixton Park**: 274.5 Acres, Subdivision (Status: Approved, 798 planned units / 185 existing units).
2. **Riverside Crossing**: 21.4 Acres, Commercial (Status: Approved).
3. **Redwood Square**: 5.1 Acres, Commercial (Status: Approved, previous name *Stevenette Development*).
4. **Canton Ridge**: 38.3 Acres, Subdivision (Status: Approved, 102 planned units / 79 existing units).

---

### 3. Gateway Overlay (`Zoning_MapServer_3`)
Contains 9 polygon features defining the spatial boundaries of the **Gateway Overlay zone**. This overlay applies special aesthetic and commercial guidelines to entrance points of the city (e.g., along major highway segments).

---

### 4. PUD Overlay (`Zoning_MapServer_0`)
Contains 11 features marking **Planned Unit Development overlays**. These allow developers higher flexibility in lot size, zoning, and building types in exchange for public open space or design enhancements.

---

### 5. Zoning (`Zoning_MapServer_1`)
This is the **core zoning map of Saratoga Springs**. It defines the zoning districts that govern what can be built on every parcel in the city.
* **Key Attribute**: `ZONECLASS` (Zoning Classification Code)
* **Zoning Districts Breakdown (Value Counts)**:
  * **`R1-10`** (80 zones): Low-Density Single Family Residential (minimum 10,000 sq ft lots).
  * **`PC`** (58 zones): Planned Community zones.
  * **`A`** (43 zones): Agricultural zones.
  * **`RC`** (40 zones): Regional Commercial zones.
  * **`MR`** (39 zones): Mixed Residential zones.
  * **`MF-10`** (14 zones): Multi-Family Residential (max 10 units/acre).
  * **`R1-9`** (12 zones): Low-Density Single Family Residential (minimum 9,000 sq ft lots).
  * **`RR`** (11 zones): Rural Residential zones.
  * **`MU`** (10 zones): Mixed Use zones.
  * **`CC`** (9 zones): Community Commercial zones.
  * **`IC`** (9 zones): Institutional/Civic zones (schools, government sites).
  * **`OW`** (7 zones): Office Warehouse zones.
  * **`MF-14` / `MF-18`** (11 zones): Multi-Family density variants (max 14/18 units/acre).

---

## 🗺️ GIS Mapping Visualizations

Below is the static overview map showing the City Boundary (red dashed line) overlaying the Zoning Districts (left) and the General Land Use categories (right).

![Planning and Zoning EDA Map](C:/Users/ajave/.gemini/antigravity-ide/brain/cd80bc04-02a9-4013-85fd-3ffecf954fae/zoning_eda_map.png)

### 🔗 Interactive Map File
An interactive Folium HTML map showing these zoning layers with full hover tooltips has been compiled and saved locally. You can open and view it directly in your browser:
* [zoning_eda_map.html](file:///C:/Users/ajave/.gemini/antigravity-ide/brain/cd80bc04-02a9-4013-85fd-3ffecf954fae/zoning_eda_map.html)

