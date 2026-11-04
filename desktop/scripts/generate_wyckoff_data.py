"""Extract pinned, licensed Moyo Hall-setting/Wyckoff data (no runtime dependency)."""
import hashlib
import json
from pathlib import Path
import re
from urllib.request import urlopen

BASE = 'https://raw.githubusercontent.com/spglib/moyo/v0.15.0/'
TARGET = Path(__file__).resolve().parents[2] / 'dioptas/resources/data/wyckoff'


def generate():
    paths = ['moyo/src/data/hall_symbol_database.rs', 'moyo/src/data/wyckoff.rs']
    sources = [urlopen(BASE + path).read() for path in paths]
    quoted = r'"(?:[^"\\]|\\.)*"'
    halls = re.findall(r'HallSymbolEntry::new\(\s*(\d+),\s*(\d+),\s*\d+,\s*(' + quoted + r'),\s*(' + quoted + r')', sources[0].decode())
    positions = re.findall(r"WyckoffPosition::new\(\s*(\d+),\s*(\d+),\s*'(.)',\s*(" + quoted + r'),\s*(' + quoted + r')', sources[1].decode())
    assert len(halls) == 530 and len(positions) == 3467
    table = {int(h): dict(number=int(n), setting=json.loads(setting), hall=json.loads(symbol), positions=[])
             for h, n, setting, symbol in halls}
    for hall, multiplicity, letter, symmetry, coordinates in positions:
        table[int(hall)]['positions'].append([int(multiplicity), letter, json.loads(symmetry), json.loads(coordinates)])
    result = dict(source=BASE, version='0.15.0',
                  source_sha256={p: hashlib.sha256(s).hexdigest() for p, s in zip(paths, sources)},
                  settings=list(table.values()))
    TARGET.mkdir(parents=True, exist_ok=True)
    (TARGET / 'positions.json').write_text(json.dumps(result, separators=(',', ':')) + '\n')
    (TARGET / 'LICENSE-MIT').write_bytes(urlopen(BASE + 'LICENSE-MIT').read())
    print(f'{len(halls)} Hall settings, {len(positions)} Wyckoff representatives')


if __name__ == '__main__':
    generate()
