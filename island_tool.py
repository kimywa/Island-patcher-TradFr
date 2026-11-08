#!/usr/bin/env python3
"""
Island Tool - patch + traduction française hors ligne pour Island 1.2.9 (Windows x64).

Usage :
    python island_tool.py patch island.exe
    python island_tool.py all-in-one island.exe

Crée une copie, ne modifie jamais l'original.
"""

import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

# ------------------------------------------------------------------
# Patches binaires identifiés (Island 1.2.9, x64)
# ------------------------------------------------------------------
PATCHES = (
    (0x158248, bytes.fromhex("83 F5 01"), bytes.fromhex("83 CD 01")),
    (0x4139A7, bytes.fromhex("41 83 3E 01"), bytes.fromhex("41 83 3E 02")),
)

# ------------------------------------------------------------------
# Regex pour repérer les paires de traduction dans les JS embarqués
# ------------------------------------------------------------------
LITERAL = r"`(?:\\.|[^`\\])*`"
PAIR = re.compile(
    r"(?P<fn>\b[A-Za-z_$][\w$]*)\(\s*(?P<ru>" + LITERAL
    + r")\s*,\s*(?P<en>" + LITERAL + r")\s*\)"
)
PATH_RE = re.compile(rb"/(?:assets|_next)/[a-zA-Z0-9_.@/% -]{1,200}")

# ------------------------------------------------------------------
# Lecture du dictionnaire de traductions
# ------------------------------------------------------------------
def read_translations(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(
            f"Dictionnaire introuvable : {path}\n"
            "Place traductions_fr.json à côté de island_tool.py."
        )
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or not value:
        raise RuntimeError("Dictionnaire vide ou invalide.")
    if not all(isinstance(k, str) and isinstance(v, str) and v.strip()
               for k, v in value.items()):
        raise RuntimeError("Le dictionnaire contient des entrées vides ou invalides.")
    return value

# ------------------------------------------------------------------
# Détection des ressources JS compressées dans l'EXE
# ------------------------------------------------------------------
def file_offset(pe, va, size, length):
    rva = va - pe.OPTIONAL_HEADER.ImageBase
    for section in pe.sections:
        begin = section.VirtualAddress
        if begin <= rva and rva + size <= begin + section.SizeOfRawData:
            off = section.PointerToRawData + rva - begin
            if 0 <= off and off + size <= length:
                return off
    return None

def offset_va(pe, offset):
    for section in pe.sections:
        begin = section.PointerToRawData
        if begin <= offset < begin + section.SizeOfRawData:
            return (pe.OPTIONAL_HEADER.ImageBase + section.VirtualAddress
                    + offset - begin)
    return None

def discover_assets(pe, data, brotli):
    assets = {}
    for match in PATH_RE.finditer(data):
        path_va = offset_va(pe, match.start())
        if path_va is None:
            continue
        needle = struct.pack("<Q", path_va)
        start = 0
        while True:
            entry = data.find(needle, start)
            if entry < 0:
                break
            start = entry + 1
            if entry + 32 > len(data):
                continue
            _, path_length, payload_va, payload_length = struct.unpack_from(
                "<QQQQ", data, entry
            )
            if not 0 < path_length < 1000 or not 0 < payload_length <= len(data):
                continue
            path_off = file_offset(pe, path_va, path_length, len(data))
            off = file_offset(pe, payload_va, payload_length, len(data))
            if path_off is None or off is None:
                continue
            try:
                path = data[path_off:path_off + path_length].decode("utf-8")
            except UnicodeDecodeError:
                continue
            if not path.startswith(("/assets/", "/_next/")):
                continue
            if not path.endswith(".js"):
                continue
            if path not in assets:
                try:
                    text = brotli.decompress(data[off:off + payload_length]).decode("utf-8")
                except Exception:
                    continue
                assets[path] = {
                    "offset": off, "size": payload_length,
                    "entries": [], "text": text,
                }
            item = assets[path]
            if (item["offset"], item["size"]) != (off, payload_length):
                raise RuntimeError(f"Ressource ambigue : {path}")
            if entry not in item["entries"]:
                item["entries"].append(entry)
    return assets

# ------------------------------------------------------------------
# Traduction des paires russes/anglaises
# ------------------------------------------------------------------
def translation_aliases(text, path):
    aliases = {"S"} if path.endswith("/createLucideIcon-CLjo64TX.js") else set()
    pattern = r'import\s*\{([^}]+)\}\s*from\s*["\']\./createLucideIcon-CLjo64TX\.js["\']'
    for match in re.finditer(pattern, text):
        for part in match[1].split(","):
            found = re.fullmatch(r"\s*V\s+as\s+([\w$]+)\s*", part)
            if found:
                aliases.add(found[1])
            elif part.strip() == "V":
                aliases.add("V")
    return aliases

def translate(text, path, cache, compact):
    aliases = translation_aliases(text, path)
    stats = {"translated": 0, "dynamic_skipped": 0, "escaped_skipped": 0}
    missing = set()

    def replace(match):
        if match["fn"] not in aliases or not re.search(r"[\u0400-\u04ff]", match["ru"]):
            return match[0]
        english = match["en"][1:-1]
        if "${" in english:
            stats["dynamic_skipped"] += 1
            return match[0]
        if "\\" in english:
            stats["escaped_skipped"] += 1
            return match[0]
        if not re.search("[A-Za-z]", english):
            return match[0]
        if english not in cache:
            missing.add(english)
            return match[0]
        french = json.dumps(cache[english], ensure_ascii=False)
        first = french if compact else match["ru"]
        stats["translated"] += 1
        return match["fn"] + "(" + first + "," + french + ")"

    result = PAIR.sub(replace, text)
    if path.startswith("/assets/settings-"):
        result = result.replace("label:`English`", "label:`Français`")
    return result, stats, missing

# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
def main():
    folder = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Island Tool : patch et/ou traduction française hors ligne (Island 1.2.9, Windows x64)."
    )
    parser.add_argument("mode", choices=["patch", "all-in-one"],
                        help="patch : applique les 2 patches binaires. all-in-one : patch + traduction française.")
    parser.add_argument("exe", type=Path, help="Chemin de l'EXE Island à traiter.")
    parser.add_argument("--cache", type=Path, default=folder / "traductions_fr.json",
                        help="Dictionnaire de traductions (défaut : traductions_fr.json à côté du script).")
    parser.add_argument("-o", "--output", type=Path, help="Chemin de sortie (optionnel).")
    parser.add_argument("--compact-fr", action="store_true",
                        help="Remplace aussi les textes russes par le français pour gagner de la place.")
    args = parser.parse_args()

    source = args.exe.resolve()
    if not source.exists():
        raise RuntimeError(f"Fichier introuvable : {source}")

    suffix = "_patched.exe" if args.mode == "patch" else "_FR.exe"
    target = (args.output or source.with_name(source.stem + suffix)).resolve()
    if source == target:
        raise RuntimeError("La sortie ne doit pas remplacer la source.")
    if target.exists():
        raise RuntimeError(f"La sortie existe déjà : {target.name}. Choisis un autre nom avec -o.")

    try:
        import pefile
        import brotli
    except ImportError as exc:
        raise RuntimeError("Installe les dépendances : python -m pip install pefile brotli") from exc

    data = source.read_bytes()
    pe = pefile.PE(data=data)
    try:
        if pe.FILE_HEADER.Machine != 0x8664:
            raise RuntimeError("Executable x86-64 attendu.")

        plan = []

        # --- Patches binaires ---
        if args.mode in ("patch", "all-in-one"):
            for rva, before, after in PATCHES:
                off = file_offset(pe, pe.OPTIONAL_HEADER.ImageBase + rva, len(before), len(data))
                if off is None:
                    raise RuntimeError(f"RVA invalide : 0x{rva:X}")
                current = data[off:off + len(before)]
                if current == after:
                    print(f"[+] Patch déjà présent à la RVA 0x{rva:X}")
                elif current == before:
                    plan.append((off, after))
                    print(f"[+] Patch vérifié à la RVA 0x{rva:X}")
                else:
                    raise RuntimeError(
                        f"Version incompatible à la RVA 0x{rva:X}. "
                        "Ce script est testé uniquement sur Island 1.2.9 x64. Aucun EXE créé."
                    )

        # --- Traduction ---
        if args.mode == "all-in-one":
            cache = read_translations(args.cache)
            assets = discover_assets(pe, data, brotli)
            if not assets:
                raise RuntimeError("Aucun JavaScript compressé reconnu.")
            report = []
            missing_all = set()
            too_large = []
            total = 0
            for path, item in sorted(assets.items()):
                translated, stats, missing = translate(item["text"], path, cache, args.compact_fr)
                missing_all.update(missing)
                if translated == item["text"]:
                    continue
                payload = translated.encode("utf-8")
                packed = brotli.compress(payload, quality=11)
                if brotli.decompress(packed) != payload:
                    raise RuntimeError("Vérification Brotli échouée.")
                size = item["size"]
                fits = len(packed) <= size
                report.append({"asset": path, **stats, "old_size": size, "new_size": len(packed), "fits": fits})
                total += stats["translated"]
                print(f"[*] {path}: {stats['translated']} textes ; {size} -> {len(packed)} octets")
                if not fits:
                    too_large.append(path)
                    continue
                plan.append((item["offset"], packed + b"\x00" * (size - len(packed))))
                for entry in item["entries"]:
                    plan.append((entry + 24, struct.pack("<Q", len(packed))))

            report_path = target.with_suffix(".rapport.json")
            report_path.write_text(json.dumps(
                {"source_sha256": hashlib.sha256(data).hexdigest(),
                 "assets": report, "missing": sorted(missing_all)},
                ensure_ascii=False, indent=2), encoding="utf-8")

            if missing_all:
                raise RuntimeError(
                    f"{len(missing_all)} textes absents du dictionnaire. "
                    "Consulte le rapport. Aucun EXE créé."
                )
            if too_large:
                raise RuntimeError(
                    "Ressources trop grandes. Aucun EXE créé. "
                    "Option possible : --compact-fr (remplace aussi les textes russes)."
                )
            if not total:
                raise RuntimeError("Aucun texte traduit. Aucun EXE créé.")

        # --- Écriture de la copie ---
        result = bytearray(data)
        for off, payload in plan:
            result[off:off + len(payload)] = payload
        if len(result) != len(data):
            raise RuntimeError("La taille du fichier a changé de façon inattendue.")
        target.write_bytes(result)
        print(f"\n[+] Créé : {target.name}")
        print(f"[+] Source inchangée. Aucun appel réseau.")
        if args.mode == "all-in-one":
            print(f"[+] {total} textes traduits. Ferme Island, lance cette copie, choisis English / Français.")
        else:
            print("[+] Ferme Island, lance cette copie.")

    finally:
        pe.close()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nAnnulé.")
    except Exception as exc:
        sys.exit(f"ERREUR : {exc}")