"""Seeded operational state extents for phased nationwide rollout.

The boxes are only viewport and coarse containment aids. Admin-uploaded state
boundaries can replace the provisional geometry before a state is marked ready.
"""
from __future__ import annotations

NIGERIA_STATES: list[dict[str, object]] = [
    {"code": "AB", "name": "Abia", "capital": "Umuahia", "centroid": [7.49, 5.53], "bbox": [7.0, 4.8, 8.3, 6.1]},
    {"code": "AD", "name": "Adamawa", "capital": "Yola", "centroid": [12.39, 9.33], "bbox": [11.0, 7.0, 14.0, 10.9]},
    {"code": "AK", "name": "Akwa Ibom", "capital": "Uyo", "centroid": [7.85, 5.01], "bbox": [7.25, 4.45, 8.55, 5.55]},
    {"code": "AN", "name": "Anambra", "capital": "Awka", "centroid": [7.06, 6.22], "bbox": [6.55, 5.65, 7.35, 6.85]},
    {"code": "BA", "name": "Bauchi", "capital": "Bauchi", "centroid": [10.32, 10.31], "bbox": [8.7, 9.3, 11.9, 12.4]},
    {"code": "BY", "name": "Bayelsa", "capital": "Yenagoa", "centroid": [6.26, 4.77], "bbox": [5.35, 4.25, 6.75, 5.35]},
    {"code": "BE", "name": "Benue", "capital": "Makurdi", "centroid": [8.75, 7.34], "bbox": [7.45, 6.4, 10.0, 8.4]},
    {"code": "BO", "name": "Borno", "capital": "Maiduguri", "centroid": [13.16, 11.84], "bbox": [11.6, 10.0, 14.7, 13.9]},
    {"code": "CR", "name": "Cross River", "capital": "Calabar", "centroid": [8.35, 5.86], "bbox": [7.75, 4.65, 9.45, 6.95]},
    {"code": "DE", "name": "Delta", "capital": "Asaba", "centroid": [6.05, 5.7], "bbox": [5.0, 5.0, 6.8, 6.55]},
    {"code": "EB", "name": "Ebonyi", "capital": "Abakaliki", "centroid": [8.06, 6.32], "bbox": [7.45, 5.75, 8.45, 6.85]},
    {"code": "ED", "name": "Edo", "capital": "Benin City", "centroid": [6.54, 6.63], "bbox": [5.0, 5.6, 7.6, 7.6]},
    {"code": "EK", "name": "Ekiti", "capital": "Ado Ekiti", "centroid": [5.31, 7.67], "bbox": [4.85, 7.25, 5.85, 8.1]},
    {"code": "EN", "name": "Enugu", "capital": "Enugu", "centroid": [7.51, 6.46], "bbox": [6.95, 5.85, 7.95, 7.05]},
    {"code": "FC", "name": "FCT", "capital": "Abuja", "centroid": [7.4913, 9.0579], "bbox": [6.75, 8.25, 7.75, 9.35]},
    {"code": "GO", "name": "Gombe", "capital": "Gombe", "centroid": [11.17, 10.28], "bbox": [10.3, 9.45, 11.95, 11.25]},
    {"code": "IM", "name": "Imo", "capital": "Owerri", "centroid": [7.04, 5.57], "bbox": [6.6, 5.1, 7.4, 6.0]},
    {"code": "JI", "name": "Jigawa", "capital": "Dutse", "centroid": [9.35, 12.23], "bbox": [8.0, 11.0, 10.7, 13.1]},
    {"code": "KD", "name": "Kaduna", "capital": "Kaduna", "centroid": [7.44, 10.52], "bbox": [6.0, 9.0, 8.8, 11.7]},
    {"code": "KN", "name": "Kano", "capital": "Kano", "centroid": [8.52, 12.0], "bbox": [7.65, 10.9, 9.35, 12.85]},
    {"code": "KT", "name": "Katsina", "capital": "Katsina", "centroid": [7.6, 12.99], "bbox": [6.85, 11.65, 8.8, 13.35]},
    {"code": "KE", "name": "Kebbi", "capital": "Birnin Kebbi", "centroid": [4.2, 11.68], "bbox": [3.5, 10.1, 6.1, 13.25]},
    {"code": "KO", "name": "Kogi", "capital": "Lokoja", "centroid": [6.74, 7.8], "bbox": [5.3, 6.5, 7.9, 8.9]},
    {"code": "KW", "name": "Kwara", "capital": "Ilorin", "centroid": [4.55, 8.5], "bbox": [2.7, 7.7, 6.0, 10.0]},
    {"code": "LA", "name": "Lagos", "capital": "Ikeja", "centroid": [3.38, 6.52], "bbox": [2.7, 6.35, 4.35, 6.75]},
    {"code": "NA", "name": "Nasarawa", "capital": "Lafia", "centroid": [8.52, 8.5], "bbox": [7.6, 7.7, 9.4, 9.4]},
    {"code": "NI", "name": "Niger", "capital": "Minna", "centroid": [6.55, 9.93], "bbox": [3.7, 8.0, 7.8, 11.8]},
    {"code": "OG", "name": "Ogun", "capital": "Abeokuta", "centroid": [3.35, 7.0], "bbox": [2.7, 6.3, 4.6, 7.9]},
    {"code": "ON", "name": "Ondo", "capital": "Akure", "centroid": [5.06, 7.1], "bbox": [4.35, 5.85, 6.1, 7.85]},
    {"code": "OS", "name": "Osun", "capital": "Osogbo", "centroid": [4.56, 7.56], "bbox": [4.0, 7.0, 5.25, 8.15]},
    {"code": "OY", "name": "Oyo", "capital": "Ibadan", "centroid": [3.93, 7.85], "bbox": [2.8, 7.0, 5.1, 9.2]},
    {"code": "PL", "name": "Plateau", "capital": "Jos", "centroid": [9.22, 9.17], "bbox": [8.35, 8.35, 10.55, 10.45]},
    {"code": "RI", "name": "Rivers", "capital": "Port Harcourt", "centroid": [6.91, 4.86], "bbox": [6.35, 4.35, 7.6, 5.6]},
    {"code": "SO", "name": "Sokoto", "capital": "Sokoto", "centroid": [5.24, 13.06], "bbox": [4.0, 11.6, 6.8, 13.9]},
    {"code": "TA", "name": "Taraba", "capital": "Jalingo", "centroid": [10.8, 7.99], "bbox": [9.0, 6.5, 12.2, 9.8]},
    {"code": "YO", "name": "Yobe", "capital": "Damaturu", "centroid": [11.75, 12.0], "bbox": [9.9, 10.5, 12.8, 13.4]},
    {"code": "ZA", "name": "Zamfara", "capital": "Gusau", "centroid": [6.22, 12.17], "bbox": [5.0, 10.8, 7.25, 13.2]},
]

NIGERIA_BBOX: tuple[float, float, float, float] = (2.65, 4.25, 14.7, 13.95)
NIGERIA_CENTER: tuple[float, float] = (8.0, 9.6)
