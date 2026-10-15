"""music21-free reference counts, read straight from MusicXML with ElementTree.

Expected NoteEvents per <part> = pitched <note> elements (rests, unpitched and
cue notes excluded; chord members and grace notes included) minus those
carrying <tie type="stop"> (they continue an earlier note). Countable by hand
from the XML.
"""
import xml.etree.ElementTree as ET
from pathlib import Path


def expected_event_counts(path: str | Path, measure_range: tuple[int, int] | None = None) -> dict[str, int]:
    """{part_name: count}. measure_range = (first, last) *indices* (0-based,
    inclusive) of <measure> elements, for slicing a movement or excerpt."""
    root = ET.parse(path).getroot()
    names = {sp.get("id"): (sp.findtext("part-name") or sp.get("id")) for sp in root.iter("score-part")}
    out = {}
    for part in root.iter("part"):
        measures = part.findall("measure")
        if measure_range is not None:
            measures = measures[measure_range[0]:measure_range[1] + 1]
        n = 0
        for m in measures:
            for nt in m.iter("note"):
                if nt.find("pitch") is None or nt.find("cue") is not None:
                    continue
                if any(t.get("type") == "stop" for t in nt.findall("tie")):
                    continue
                n += 1
        out[names[part.get("id")]] = n
    return out


def read_xml_text(path: str | Path) -> str:
    import zipfile
    path = Path(path)
    if path.suffix.lower() != ".mxl":
        return path.read_text(encoding="utf-8")
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.endswith(".xml") and not n.startswith("META-INF"))
        return z.read(name).decode("utf-8")


def expected_event_counts_text(text: str, measure_range=None) -> dict[str, int]:
    import io
    return expected_event_counts(io.StringIO(text), measure_range)


def movement_measure_range(text: str, movement: int) -> tuple[int, int]:
    """0-based inclusive <measure> index range of a movement, split where the
    first part's measure numbers reset (same rule as the parser)."""
    import io, re
    root = ET.parse(io.StringIO(text)).getroot()
    # Non-numeric numbers ("X1": MuseScore measures excluded from the count)
    # carry the previous number, so they never look like a reset.
    nums, prev = [], 0
    for m in root.find("part").findall("measure"):
        mt = re.match(r"\d+", m.get("number") or "")
        prev = int(mt.group()) if mt else prev
        nums.append(prev)
    bounds = [0] + [i for i in range(1, len(nums)) if nums[i] < nums[i - 1]] + [len(nums)]
    a, b = bounds[movement - 1], bounds[movement]
    return a, b - 1


def grace_count(text: str) -> int:
    import io
    root = ET.parse(io.StringIO(text)).getroot()
    return sum(1 for n in root.iter("note") if n.find("grace") is not None and n.find("pitch") is not None)
