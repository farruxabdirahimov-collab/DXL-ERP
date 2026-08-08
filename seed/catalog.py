"""DXL boshlang'ich katalogi (~100 SKU).

DIQQAT: bu namunaviy katalog — tipik implant o'lchamlari panjarasi asosida
tuzilgan. Haqiqiy prays-listingizni Excel'da yuklab, ustidan yozishingiz mumkin:
    Katalog -> Excel'ga yuklash -> to'ldirish -> Import qilish
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, asdict
from decimal import Decimal
from pathlib import Path

CSV_PATH = Path(__file__).with_name("dxl_products.csv")

CATEGORIES: list[tuple[str, str, int]] = [
    ("implant", "Implantlar", 10),
    ("abutment", "Abatmentlar", 20),
    ("healing", "Sog'aytiruvchi vintlar", 30),
    ("cover", "Yopqich vintlar", 40),
    ("multiunit", "Multi-unit tizimi", 50),
    ("instrument", "Jarrohlik asboblari", 60),
    ("biomaterial", "Suyak materiali va membrana", 70),
]


@dataclass
class SeedProduct:
    sku: str
    name: str
    category: str
    diameter_mm: str
    length_mm: str
    implant_type: str
    connection_type: str
    price_usd: str
    min_stock: str


def _implants() -> list[SeedProduct]:
    """Implantlar — asosiy tahlil kesimi (diametr x uzunlik x tur)."""
    families = [
        # (kod, nomi, ulanish, diametrlar, uzunliklar, bazaviy narx)
        (
            "BL",
            "Bone Level",
            "Internal hex",
            [3.3, 3.8, 4.3, 4.8, 5.5],
            [8.0, 10.0, 11.5, 13.0, 15.0],
            Decimal("85"),
        ),
        (
            "TL",
            "Tissue Level",
            "Internal octagon",
            [3.5, 4.1, 4.8, 5.5],
            [8.0, 10.0, 12.0, 14.0],
            Decimal("92"),
        ),
        (
            "KN",
            "Konus",
            "Conical",
            [3.5, 4.0, 4.5, 5.0],
            [8.5, 10.0, 11.5, 13.0],
            Decimal("98"),
        ),
    ]

    result: list[SeedProduct] = []
    for code, type_name, connection, diameters, lengths, base_price in families:
        for diameter in diameters:
            for length in lengths:
                # Yo'g'onroq va uzunroq implant biroz qimmatroq
                price = base_price + Decimal(str(round((diameter - 3.3) * 4, 2))) + Decimal(
                    str(round((length - 8.0) * 1.5, 2))
                )
                # Eng ko'p ishlatiladigan o'lchamlar zaxirasi kattaroq
                popular = diameter in (3.8, 4.0, 4.1, 4.3) and length in (10.0, 11.5, 12.0)
                result.append(
                    SeedProduct(
                        sku=f"DXL-{code}-{diameter:g}x{length:g}".replace(".", ""),
                        name=f"DXL {type_name} implant {diameter:g}x{length:g} mm",
                        category="implant",
                        diameter_mm=f"{diameter:g}",
                        length_mm=f"{length:g}",
                        implant_type=type_name,
                        connection_type=connection,
                        price_usd=f"{price:.2f}",
                        min_stock="10" if popular else "5",
                    )
                )
    return result


def _components() -> list[SeedProduct]:
    result: list[SeedProduct] = []

    # Abatmentlar: diametr x milya balandligi
    for diameter in (3.5, 4.0, 4.5, 5.0):
        for gingiva in (1.0, 2.0, 3.0):
            result.append(
                SeedProduct(
                    sku=f"DXL-AB-{diameter:g}-G{gingiva:g}".replace(".", ""),
                    name=f"DXL abatment {diameter:g} mm, gingival {gingiva:g} mm",
                    category="abutment",
                    diameter_mm=f"{diameter:g}",
                    length_mm="",
                    implant_type="Abatment",
                    connection_type="Internal hex",
                    price_usd=f"{28 + diameter * 2 + gingiva:.2f}",
                    min_stock="6",
                )
            )

    # Sog'aytiruvchi vintlar
    for diameter in (3.5, 4.0, 4.5, 5.0):
        for height in (2.0, 3.0, 4.0):
            result.append(
                SeedProduct(
                    sku=f"DXL-HC-{diameter:g}-H{height:g}".replace(".", ""),
                    name=f"DXL sog'aytiruvchi vint {diameter:g} mm, balandlik {height:g} mm",
                    category="healing",
                    diameter_mm=f"{diameter:g}",
                    length_mm=f"{height:g}",
                    implant_type="Healing cap",
                    connection_type="Internal hex",
                    price_usd=f"{12 + height:.2f}",
                    min_stock="10",
                )
            )

    # Yopqich vintlar
    for diameter in (3.3, 3.8, 4.3, 4.8):
        result.append(
            SeedProduct(
                sku=f"DXL-CS-{diameter:g}".replace(".", ""),
                name=f"DXL yopqich vint {diameter:g} mm",
                category="cover",
                diameter_mm=f"{diameter:g}",
                length_mm="",
                implant_type="Cover screw",
                connection_type="Internal hex",
                price_usd="6.50",
                min_stock="15",
            )
        )

    # Multi-unit tizimi
    for angle in (0, 17, 30):
        for gingiva in (1.0, 3.0):
            result.append(
                SeedProduct(
                    sku=f"DXL-MU-{angle}-G{gingiva:g}".replace(".", ""),
                    name=f"DXL multi-unit abatment {angle}°, gingival {gingiva:g} mm",
                    category="multiunit",
                    diameter_mm="",
                    length_mm="",
                    implant_type="Multi-unit",
                    connection_type="Conical",
                    price_usd=f"{48 + angle * 0.6 + gingiva:.2f}",
                    min_stock="4",
                )
            )

    # Jarrohlik asboblari
    instruments = [
        ("DXL-DR-20", "DXL pilot bur 2.0 mm", "42.00", 3),
        ("DXL-DR-28", "DXL bur 2.8 mm", "45.00", 3),
        ("DXL-DR-33", "DXL bur 3.3 mm", "45.00", 3),
        ("DXL-DR-38", "DXL bur 3.8 mm", "48.00", 3),
        ("DXL-DR-43", "DXL bur 4.3 mm", "48.00", 3),
        ("DXL-KIT-BASIC", "DXL jarrohlik to'plami (asosiy)", "390.00", 1),
        ("DXL-RTCH", "DXL raxovik (ratchet) kaliti", "120.00", 2),
        ("DXL-TRQ", "DXL dinamometrik kalit", "165.00", 2),
    ]
    for sku, name, price, min_stock in instruments:
        result.append(
            SeedProduct(
                sku=sku,
                name=name,
                category="instrument",
                diameter_mm="",
                length_mm="",
                implant_type="Asbob",
                connection_type="",
                price_usd=price,
                min_stock=str(min_stock),
            )
        )

    # Biomateriallar
    biomaterials = [
        ("DXL-BG-05", "DXL suyak materiali 0.5 g", "58.00", 6),
        ("DXL-BG-10", "DXL suyak materiali 1.0 g", "96.00", 6),
        ("DXL-MEM-1520", "DXL kollagen membrana 15x20 mm", "72.00", 5),
        ("DXL-MEM-2530", "DXL kollagen membrana 25x30 mm", "110.00", 4),
    ]
    for sku, name, price, min_stock in biomaterials:
        result.append(
            SeedProduct(
                sku=sku,
                name=name,
                category="biomaterial",
                diameter_mm="",
                length_mm="",
                implant_type="Biomaterial",
                connection_type="",
                price_usd=price,
                min_stock=str(min_stock),
            )
        )

    return result


def build_catalog() -> list[SeedProduct]:
    return _implants() + _components()


def write_csv(path: Path | None = None) -> Path:
    path = path or CSV_PATH
    products = build_catalog()
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(products[0]).keys()))
        writer.writeheader()
        for product in products:
            writer.writerow(asdict(product))
    return path


def read_csv(path: Path | None = None) -> list[dict]:
    path = path or CSV_PATH
    if not path.exists():
        return [asdict(p) for p in build_catalog()]
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


if __name__ == "__main__":  # pragma: no cover
    written = write_csv()
    print(f"{len(build_catalog())} ta mahsulot yozildi: {written}")
