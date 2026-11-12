#!/usr/bin/env python3
"""Reference implementation of the APIs.json aid specification.

  python3 aid.py lint apis.yml [more ...]     check documents; exit 1 on any MUST failure
  python3 aid.py census <dir> [--json out]    check every <dir>/*/apis.yml and summarise
  python3 aid.py derive <domain>              suggest a provider aid for a domain
  python3 aid.py slug <provider-aid> "<API name>"   suggest an API aid

MUST rules are errors; SHOULD rules are warnings. Warnings never fail a lint, because
existing aids are page slugs and stay valid -- see "Stability" in README.md.
"""
import collections
import json
import os
import re
import sys

try:
    import yaml
    Loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
except ImportError:
    sys.exit("Requires pyyaml:  pip install pyyaml")

SEGMENT = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
API_AID = re.compile(r"^([a-z0-9]+(?:-[a-z0-9]+)*):([a-z0-9]+(?:-[a-z0-9]+)*)$")
ARTIFACT_WORDS = re.compile(r"(^|-)(openapi|swagger|asyncapi|json|yaml|yml|spec|specification)(-|$)")
VERSION = re.compile(r"(^|-)v\d+(-\d+)*$")
COMMON_TLDS = ("com", "io", "ai", "net", "org", "co", "dev", "app", "tech", "us", "gov", "edu")
DERIVE_STRIP = re.compile(r"(^|-)(openapi|swagger|asyncapi|yaml|yml|spec|specification)(?=-|$)")
GENERIC = {"api", "apis", "rest-api", "public-api", "main", "default", "core", "v1", "v2"}


def derive_provider_aid(domain):
    """Domain -> provider aid (SHOULD rule P1). Keeps the TLD as a hyphenated suffix;
    a catalog MAY drop a .com suffix when the remaining name is unambiguous."""
    host = re.sub(r"^https?://", "", domain.strip().lower()).split("/")[0]
    host = re.sub(r"^(www|api|developer|developers|docs)\.", "", host)
    aid = re.sub(r"[^a-z0-9]+", "-", host).strip("-")
    return re.sub(r"-{2,}", "-", aid)


def derive_api_slug(provider_aid, name):
    """API name -> API aid (SHOULD rules A1-A4)."""
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    for p in sorted({provider_aid, provider_aid.split("-")[0]}, key=len, reverse=True):
        if s.startswith(p + "-"):
            s = s[len(p) + 1:]
            break
    s = DERIVE_STRIP.sub("-", s).strip("-")  # keeps json: JSON-RPC is a protocol, not a format
    s = re.sub(r"(-api)+$", "", s)
    s = re.sub(r"-{2,}", "-", s).strip("-") or "api"
    return f"{provider_aid}:{s}"


def check_provider(aid, dirname=None):
    errs, warns = [], []
    if aid is None:
        return ["M1 provider aid missing"], warns
    if not isinstance(aid, str):
        return [f"M2 provider aid is not a string: {aid!r}"], warns
    if not SEGMENT.match(aid):
        errs.append(f"M2 provider aid {aid!r} does not match ^[a-z0-9]+(-[a-z0-9]+)*$")
    if not 2 <= len(aid) <= 64:
        errs.append(f"M3 provider aid {aid!r} is {len(aid)} chars (2-64)")
    if dirname and aid != dirname:
        errs.append(f"M6 provider aid {aid!r} != its repository/directory {dirname!r}")
    if len(aid) > 40:
        warns.append(f"P2 provider aid {aid!r} is long ({len(aid)} chars); prefer domain or acronym-domain")
    return errs, warns


def check_api(aid, provider):
    errs, warns = [], []
    if aid is None:
        return ["M1 API entry has no aid"], warns
    if not isinstance(aid, str):
        return [f"M2 API aid is not a string: {aid!r}"], warns
    if "\n" in aid or len(aid) > 128:
        errs.append(f"M3 API aid {aid[:60]!r}... is {len(aid)} chars (max 128, one line)")
    m = API_AID.match(aid)
    if not m:
        why = "no colon" if ":" not in aid else ("reserved extra segment" if aid.count(":") > 1 else "bad characters")
        errs.append(f"M2 API aid {aid!r} is not <provider-aid>:<api-slug> ({why})")
        return errs, warns
    pre, slug = m.groups()
    if provider and pre != provider:
        errs.append(f"M4 API aid {aid!r} prefix {pre!r} != provider aid {provider!r}")
    if slug == pre or slug.startswith(pre + "-"):
        warns.append(f"A1 API aid {aid!r} repeats the provider in the slug")
    if slug.endswith("-api") or slug == "api":
        warns.append(f"A2 API aid {aid!r} ends in -api")
    if ARTIFACT_WORDS.search(slug):
        warns.append(f"A3 API aid {aid!r} names an artifact format, not the API")
    if VERSION.search(slug):
        warns.append(f"A4 API aid {aid!r} carries a version")
    if slug in GENERIC:
        warns.append(f"A5 API aid {aid!r} is generic")
    return errs, warns


def check_document(doc, dirname=None):
    if not isinstance(doc, dict):
        return ["document is not a mapping"], [], None, []
    provider = doc.get("aid")
    errs, warns = check_provider(provider, dirname)
    api_aids = []
    seen = collections.Counter()
    for i, api in enumerate(doc.get("apis") or []):
        if not isinstance(api, dict):
            continue
        a = api.get("aid")
        e, w = check_api(a, provider if isinstance(provider, str) else None)
        errs += [f"apis[{i}] {x}" for x in e]
        warns += [f"apis[{i}] {x}" for x in w]
        if isinstance(a, str):
            seen[a] += 1
            api_aids.append(a)
    errs += [f"M5 API aid {a!r} appears {n} times in one document" for a, n in seen.items() if n > 1]
    return errs, warns, provider, api_aids


def load(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return yaml.load(f, Loader=Loader)


def lint(paths):
    failed = 0
    for p in paths:
        try:
            errs, warns, _, _ = check_document(load(p))
        except yaml.YAMLError as e:
            errs, warns = [f"YAML parse error: {e}"], []
        for x in errs:
            print(f"{p}: ERROR {x}")
        for x in warns:
            print(f"{p}: warn  {x}")
        print(f"{p}: {'FAIL' if errs else 'ok'} ({len(errs)} errors, {len(warns)} warnings)")
        failed += bool(errs)
    return 1 if failed else 0


def census(root, out=None):
    rule = lambda s: s.split(" ")[0] if s[0] in "MAP" else s.split(" ")[1]
    C, R = collections.Counter(), collections.Counter()
    ex = collections.defaultdict(list)
    prov_owner, api_owner = collections.defaultdict(list), collections.defaultdict(set)
    for d in sorted(os.listdir(root)):
        p = os.path.join(root, d, "apis.yml")
        if d.startswith((".", "_", "0-")) or not os.path.isfile(p):
            continue
        C["documents"] += 1
        try:
            doc = load(p)
        except yaml.YAMLError:
            C["yaml_errors"] += 1
            continue
        errs, warns, prov, apis = check_document(doc, d)
        C["api_aids"] += len(apis)
        C["api_entries"] += len([a for a in (doc.get("apis") or []) if isinstance(a, dict)]) if isinstance(doc, dict) else 0
        C["documents_failing"] += bool(errs)
        for x in errs + warns:
            k = re.sub(r"^apis\[\d+\] ", "", x).split(" ")[0]
            R[k] += 1
            if len(ex[k]) < 6:
                ex[k].append(f"{d}: {x}")
        if isinstance(prov, str):
            prov_owner[prov].append(d)
        for a in apis:
            api_owner[a].add(d)
    dup_p = {k: v for k, v in prov_owner.items() if len(v) > 1}
    dup_a = {k: sorted(v) for k, v in api_owner.items() if len(v) > 1}
    R["M7-provider-collision"], R["M7-api-collision"] = len(dup_p), len(dup_a)
    ex["M7-provider-collision"] = [f"{k}: {v}" for k, v in list(dup_p.items())[:10]]
    ex["M7-api-collision"] = [f"{k}: {v[:4]}" for k, v in list(dup_a.items())[:10]]
    res = {"counts": dict(C), "rules": dict(sorted(R.items())), "examples": ex}
    print(json.dumps({"counts": res["counts"], "rules": res["rules"]}, indent=1))
    if out:
        with open(out, "w") as f:
            json.dump(res, f, indent=1)
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    cmd, rest = a[0], a[1:]
    if cmd == "lint":
        sys.exit(lint(rest))
    if cmd == "census":
        out = rest[rest.index("--json") + 1] if "--json" in rest else None
        sys.exit(census(rest[0], out))
    if cmd == "derive":
        print(derive_provider_aid(rest[0]))
    elif cmd == "slug":
        print(derive_api_slug(rest[0], rest[1]))
    else:
        sys.exit(__doc__)
