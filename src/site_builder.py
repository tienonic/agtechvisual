"""Adapt the public dashboard snapshot to the shared research explorer."""

from __future__ import annotations

from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import re

from src.public_ai import load_public_ai, PRIVATE_PATH

SOURCE_URL = "https://github.com/tienonic/agtechvisual"
RECORD_FIELDS = {
    "name", "category", "country", "hq_state", "status", "website", "funding",
    "funding_rounds", "description", "sources", "data_richness", "wayback_url",
}
ASSETS = (
    "explorer.js", "explorer.css", "city.js",
    "vendor/OFL.txt", "vendor/source-serif-4-latin.woff2",
)
CATEGORY_LABELS = {
    "PRECISION_AG": "Precision agriculture", "FARM_SOFTWARE": "Farm software",
    "BIOTECH": "Biotechnology", "ROBOTICS": "Robotics", "SUPPLY_CHAIN": "Supply chain",
    "WATER_IRRIGATION": "Water and irrigation", "INDOOR_CEA": "Indoor agriculture",
    "AG_FINTECH": "Agricultural finance", "LIVESTOCK": "Livestock",
    "FOOD_SAFETY": "Food safety", "AG_BIOCONTROL": "Biological pest control",
    "CONNECTIVITY": "Connectivity", "UNKNOWN": "Unclassified",
}
FORBIDDEN = PRIVATE_PATH


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_snapshot(data):
    if set(data) != {"companies", "stats"} or not isinstance(data["companies"], list):
        raise ValueError("The public snapshot must contain companies and stats.")
    for record in data["companies"]:
        if set(record) != RECORD_FIELDS:
            raise ValueError("The public record fields changed; review the publication allowlist.")
        if not isinstance(record["name"], str) or not record["name"]:
            raise ValueError("Every record needs a source name.")
        if record["status"] not in {"LIVE", "DEAD", "UNKNOWN"}:
            raise ValueError("Unexpected website observation.")
        if any(set(round_) != {"amount", "type", "date"} for round_ in record["funding_rounds"]):
            raise ValueError("The funding fields changed; review the publication allowlist.")
    if data["stats"]["total"] != len(data["companies"]):
        raise ValueError("The snapshot total does not match its records.")
    if FORBIDDEN.search(encode(data)):
        raise ValueError("The public snapshot contains a private or local path.")


def adapt(data):
    validate_snapshot(data)
    names = Counter()
    nodes, details = [], {}
    for index, record in enumerate(data["companies"]):
        name = record["name"]
        names[name] += 1
        record_id = "source-record:" + digest(name.encode())[:20] + f":{names[name]:03d}"
        shard = index // 100
        group = CATEGORY_LABELS.get(record["category"], record["category"])
        country = record["country"] or "Country not recorded"
        node = {
            "id": record_id, "label": name, "kind": "Company record",
            "group": group, "subgroup": country,
            "description": record["description"],
            "sourceUrl": SOURCE_URL,
            "status": "Website: " + {"LIVE": "Live", "DEAD": "Dead", "UNKNOWN": "Not recorded"}[record["status"]],
            "date": "", "detailUrl": f"details/agtech-{shard:03d}.json",
            "metrics": {
                "Country": country, "State": record["hq_state"],
                "Saved funding": {"value": record["funding"],
                    "unit": "USD", "note": "Sum of saved rounds; date coverage varies. A zero means no positive amount was saved, not no funding."},
                "Source labels": ", ".join(record["sources"]),
                "Observation date": None,
            },
        }
        nodes.append(node)
        details.setdefault(shard, {})[record_id] = {
            "record": record,
            "meaning": {
                "status": "Website observation, not company operating status. The observation date was not saved in the public reader.",
                "funding": "Sum of saved funding-round amounts in USD, not valuation. Total-raised estimates and individual rounds may overlap; compare the saved rounds before adding amounts.",
                "identity": "One saved source record. Repeated names remain separate; no entity match or relationship is inferred.",
                "category": "Saved classification; source descriptions may be incomplete or misclassified.",
                "source_labels": "Collector labels preserved as saved; the public reader did not include per-label source URLs.",
            },
        }
    return {
        "id": "agtech", "label": "Agricultural technology", "nodes": nodes, "edges": [],
        "view": {
            "cityHeight": {
                "metric": "Saved funding", "scale": "log", "label": "Saved funding (USD)",
                "note": "Sum of saved rounds, not valuation. Zero means no positive amount was saved, not no funding.",
            },
            "color": {
                "field": "status", "label": "Website observation",
                "values": [
                    {"value": "Website: Live", "label": "Live", "light": "#6C9FA6", "dark": "#70A7AF"},
                    {"value": "Website: Not recorded", "label": "Not recorded", "light": "#B7BBC3", "dark": "#878C98"},
                    {"value": "Website: Dead", "label": "Dead", "light": "#B68A48", "dark": "#CEAA6C"},
                ],
            },
            "groupsLast": ["Unclassified"],
        },
    }, details


METHOD = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sources and methods · Carrot Core</title><style>body{max-width:760px;margin:48px auto;padding:0 20px;font:17px/1.6 Arial,sans-serif;color:#141414}a{color:#0036a3}h1{font-family:Georgia,serif;font-weight:400}li{margin-bottom:12px}</style><body><a href="index.html">Carrot Core</a><h1>Sources and methods</h1><p>Home offers two public datasets. The agricultural technology collection contains 2,695 company records. The AI business map contains 5,715 source records plus 8 named relationship endpoints and 407 saved connections. Selecting both keeps each dataset's records and connections separate; it creates no cross-dataset relationships. <a href="data/ai-import-receipt.json">AI import provenance</a> records the exact imported files and hashes.</p><p>This catalog preserves the company records in the existing public agricultural technology reader. It is a research collection, not a complete registry. Categories and descriptions retain their saved values, including incomplete descriptions and possible classification errors.</p><ul><li>Each cell represents one saved record. Categories and countries organize the map. No company relationships were supplied, so this dataset has no connection edges. City height shows saved funding in USD on a logarithmic scale. Positive saved amounts rise above the base; records with no positive saved amount stay at the base. AI city heights continue to show connection counts. Each dataset uses its own height measure when both are loaded.</li><li>Colors show Live, Not recorded and Dead, the saved website observations. They do not describe whether a company operates today. Observation dates were absent from the public reader.</li><li>Funding is the sum of saved round amounts in USD, not valuation. Individual rounds and total-raised estimates can overlap. Zero means no positive amount was saved, not no funding. Review the original rounds before making comparisons.</li><li>Every original record field is available in the lazy source evidence panel. Source labels are collector names; per-label source URLs and database IDs were not in the public reader.</li><li>Record IDs use the exact saved name and a duplicate ordinal. Names are not merged. A changed name creates a new ID; duplicate order follows the saved source order.</li></ul><p><a href="analytical.html">Original analytical reader</a> retains Global, US and California filters, Classified, Funded and All filters, and Funding and Count sizing. Funding sizing follows that reader's logarithmic scaling; compare exact USD values in record details.</p><p><a href="data/public-dashboard.json">Complete public snapshot</a> · <a href="data/public-provenance.json">Snapshot provenance</a> · <a href="https://github.com/tienonic/agtechvisual">Collector source and update workflow</a></p><p>The shared explorer uses an original implementation of the AxiomMath Stacks visual pattern. Source Serif 4 is distributed under the <a href="explorer-assets/vendor/OFL.txt">SIL Open Font License</a>.</p></body></html>"""


def render_shell(template, prefix=""):
    config = {
        "title": "Carrot Core", "manifestUrl": prefix + "explorer-data/manifest.json",
        "defaultDatasets": ["agtech"], "legacyUrl": "analytical.html",
        "assetBase": prefix + "explorer-assets/",
        "fontUrl": prefix + "explorer-assets/vendor/source-serif-4-latin.woff2",
    }
    page = re.sub(r"<!-- Placeholders,.*?-->", "", template, count=1, flags=re.S)
    page = page.replace("__EXPLORER_TITLE__", html.escape(config["title"]))
    page = page.replace("__ASSET_BASE__", config["assetBase"])
    page = page.replace("__EXPLORER_CONFIG_JSON__", encode(config).replace("</", "<\\/"))
    page = page.replace("</head>", '<script>window.EXPLORER_CONFIG=JSON.parse(document.getElementById("explorer-config").textContent);</script></head>', 1)
    page = page.replace('<p class="lede">', '<p><a href="methods.html">Sources and methods</a> · <a href="analytical.html">Original analytical reader</a></p><p class="lede">', 1)
    return "\n".join(line.rstrip() for line in page.splitlines()) + "\n"


def build_site(root: Path, output: Path):
    root, output = root.resolve(), output.resolve()
    if output == root or root not in output.parents or output.is_symlink():
        raise ValueError("Build into a separate public directory.")
    snapshot_path = root / "data/public-dashboard.json"
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    provenance = json.loads((root / "data/public-provenance.json").read_text(encoding="utf-8"))
    if provenance["snapshotSha256"] != digest(snapshot_path.read_bytes()) or provenance["recordCount"] != len(data["companies"]):
        raise ValueError("The public snapshot does not match its saved provenance.")
    dataset, details = adapt(data)
    engine = root / "web/explorer"
    release = json.loads((engine / "release.json").read_text())
    for name in ("index.template.html", *ASSETS):
        path = engine / name
        if path.is_symlink() or digest(path.read_bytes()) != release["files"][name]:
            raise ValueError(f"The shared asset hash changed: {name}")
    template = (engine / "index.template.html").read_text(encoding="utf-8")
    ai_receipt, ai_artifacts = load_public_ai(root / "data/public-ai")
    method = METHOD.replace("2,695 company records", f"{len(dataset['nodes']):,} company records")
    method = method.replace("5,715 source records", f"{ai_receipt['sourceRecordCount']:,} source records")
    method = method.replace("8 named relationship endpoints and 407 saved connections", f"{ai_receipt['relationshipEndpointCount']} named relationship endpoints and {ai_receipt['dataset']['edgeCount']} saved connections")
    files = {
        "index.html": render_shell(template).encode(),
        "methods.html": method.encode(),
        "analytical.html": (root / "analytical.html").read_bytes(),
        "data/public-dashboard.json": snapshot_path.read_bytes(),
        "data/public-provenance.json": (root / "data/public-provenance.json").read_bytes(),
        "explorer-data/agtech.json": (encode(dataset) + "\n").encode(),
        "CNAME": (root / "CNAME").read_bytes(), ".nojekyll": b"",
    }
    manifest = {
        "schemaVersion": 1, "defaultSelection": ["agtech"],
        "datasets": [{"id": "agtech", "label": "Agricultural technology",
            "description": f"{len(dataset['nodes']):,} saved company records grouped by category and country. Website observations and funding retain their source limits. Record observation dates were not saved.",
            "nodeCount": len(dataset["nodes"]), "edgeCount": 0, "url": "agtech.json",
            "updatedAt": "", "public": True, "sourceUrl": SOURCE_URL}],
    }
    manifest["datasets"].append(ai_receipt["dataset"])
    for name, content in ai_artifacts.items():
        files["explorer-data/" + name] = content
    files["data/ai-import-receipt.json"] = (root / "data/public-ai/import-receipt.json").read_bytes()
    files["explorer-data/manifest.json"] = (encode(manifest) + "\n").encode()
    for shard, records in details.items():
        files[f"explorer-data/details/agtech-{shard:03d}.json"] = (encode({
            "schemaVersion": 1, "datasetId": "agtech", "records": records,
        }) + "\n").encode()
    for name in ASSETS:
        files["explorer-assets/" + name] = (engine / name).read_bytes()
    for name, content in files.items():
        if not name.endswith(".woff2") and FORBIDDEN.search(content.decode("utf-8")):
            raise ValueError(f"Private or local path in public file: {name}")
    receipt = {
        "schemaVersion": 1,
        "sourceRecordCount": len(dataset["nodes"]) + ai_receipt["sourceRecordCount"],
        "nodeCount": len(dataset["nodes"]) + ai_receipt["dataset"]["nodeCount"],
        "edgeCount": ai_receipt["dataset"]["edgeCount"],
        "datasets": {
            "agtech": {"sourceRecordCount": len(dataset["nodes"]), "nodeCount": len(dataset["nodes"]), "edgeCount": 0},
            "ai": {"sourceRecordCount": ai_receipt["sourceRecordCount"], "relationshipEndpointCount": ai_receipt["relationshipEndpointCount"],
                "nodeCount": ai_receipt["dataset"]["nodeCount"], "edgeCount": ai_receipt["dataset"]["edgeCount"]},
        },
        "snapshotSha256": digest(snapshot_path.read_bytes()),
        "engine": release["files"],
        "files": {name: {"sha256": digest(content), "bytes": len(content)} for name, content in sorted(files.items())},
    }
    files["build-receipt.json"] = (json.dumps(receipt, indent=2) + "\n").encode()
    output.mkdir(parents=True, exist_ok=True)
    if any(path.is_symlink() for path in output.rglob("*")):
        raise ValueError("The public build directory contains a symbolic link.")
    for path in output.rglob("*"):
        if path.is_file() and path.relative_to(output).as_posix() not in files:
            raise ValueError("Unexpected file in public build; use a fresh output directory.")
    for name, content in files.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (root / "index.html").write_text(render_shell(template, output.relative_to(root).as_posix() + "/"), encoding="utf-8")
    (root / "methods.html").write_text(method, encoding="utf-8")
    return receipt
