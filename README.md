# aid — the APIs.json API Identifier

`aid` is the property that names a provider, and each of its APIs, in an [APIs.json](https://apisjson.org) /
`apis.yml` document. Catalogs use it as the primary key for indexing, the slug for pages, the join key
between artifacts (OpenAPI, AI preferences, plans, rules), and the handle for search and filtering. This
repository makes it a formal [API Commons](https://apicommons.org) standard: a grammar, a set of rules,
a JSON Schema, a reference linter, and a census of how the property is used at scale today.

**Version 0.1.0 — draft, 2026-11-12.**

```yaml
aid: stripe                       # provider aid
apis:
  - aid: stripe:payment-intents   # API aid = <provider aid>:<api slug>
  - aid: stripe:customers
```

## Why now

APIs.json has carried `aid` since its first versions, but only by convention: lowercase, hyphens, a colon
between provider and API. The [apis.io](https://apis.io) catalog now holds **41,092** `apis.yml` documents
and **193,626** API aids, which is enough to see where the convention holds and where it breaks. Most of it
holds. What breaks is concentrated, and it breaks in the places that matter most for indexing: missing
identifiers, prefixes that point at the wrong provider, and the same aid owned by two documents.

## The grammar

```abnf
provider-aid = segment                    ; 2-64 characters
api-aid      = provider-aid ":" api-slug  ; at most 128 characters, one line
api-slug     = segment
segment      = word *( "-" word )
word         = 1*( %x61-7A / DIGIT )      ; a-z 0-9
```

As a regular expression: provider `^[a-z0-9]+(-[a-z0-9]+)*$`, API `^[a-z0-9]+(-[a-z0-9]+)*:[a-z0-9]+(-[a-z0-9]+)*$`.

No uppercase, dots, underscores, spaces, leading or trailing hyphens, or doubled hyphens. A third
`:`-separated segment is **reserved** (for example for versions or operations) and MUST NOT be used in 0.1.

## Rules

**MUST** rules make an aid usable as a key. A document that breaks one fails validation.

| Rule | Requirement |
|---|---|
| **M1** | The document has a top-level `aid`, and every entry in `apis[]` has an `aid`. |
| **M2** | Each aid matches the grammar. |
| **M3** | A provider aid is 2–64 characters. An API aid is at most 128 characters and fits on one line. |
| **M4** | An API aid's prefix (before the colon) equals the document's provider aid. |
| **M5** | An API aid appears only once in a document. |
| **M6** | Where a catalog stores one document per directory or repository, the provider aid equals that name. |
| **M7** | Within a catalog, a provider aid belongs to one document and an API aid to one provider. |
| **M8** | An aid is never reissued to a different entity. When an entity is renamed, its old aid goes into `x-aid-aliases`, and the catalog resolves (redirects) it to the new one. |

**SHOULD** rules make an aid meaningful. Breaking one raises a warning, never a failure (see *Stability*).

| Rule | Recommendation |
|---|---|
| **P1** | Derive the provider aid from the provider's registrable domain: `typesafe.ai` → `typesafe-ai`. Drop the TLD only when the remaining name is unambiguous and not a common word: `stripe.com` → `stripe` is fine, but bare `typesafe` matched two unrelated companies. |
| **P2** | Keep provider aids under 40 characters. For long institutional names, use the domain (`cdc-gov`), not the spelled-out name. |
| **A1** | The API slug names the API, not the provider: `stripe:customers`, not `stripe:stripe-customers`. The prefix already says whose it is. |
| **A2** | No trailing `-api`. Every aid identifies an API, so the suffix adds nothing. |
| **A3** | Name the API, not an artifact format. No `openapi`, `swagger`, `json`, `yaml` or `spec` in the slug. |
| **A4** | Leave versions out of the slug unless the catalog lists two versions as separate APIs side by side. |
| **A5** | Avoid generic slugs (`api`, `apis`, `rest-api`) unless the provider truly has a single API. Even then, a name is better. |

## Stability

An aid is an identifier, not a label. It is the page slug and the key other artifacts point at, so
changing it moves every URL and breaks every join. Three things follow:

1. **Existing aids that pass the MUST rules stay valid**, even if they break SHOULD rules. `stripe:stripe-accounts-api` is a legal 0.1 aid.
2. **Apply the SHOULD rules when an aid is created**, not by renaming the catalog in bulk.
3. **A rename is an alias, never an edit.** Write the new aid, record the old one in `x-aid-aliases`, and redirect.

A catalog MAY also compute a *display form* for search results (`stripe:accounts` for
`stripe:stripe-accounts-api`). A display form is never stored as the identifier.

## Using aids for indexing, search and filtering

- **Prefix scoping.** Everything a provider publishes is `<provider-aid>:*`, so a single prefix query covers the provider, with no join.
- **Cross-artifact joins.** Other API Commons documents ([AI Preferences](https://github.com/api-commons/ai-preferences), plans, rate limits, rules) carry `aid` as their key, so an artifact attaches to its provider or API without fuzzy name matching.
- **Tokenization.** Split on `:` and `-` for search. The A1/A2 rules exist partly so the tokens left are the ones that describe the API (`payment`, `intents`), not the provider's name over again plus `api`.
- **Resolution.** Resolve aliases (M8) before lookup, so old links and old artifacts still land.

## Census: the apis.io catalog, 2026-11-12

`python3 aid.py census` over 41,092 `apis.yml` documents, with full YAML parsing. Raw output is in
[`census/2026-11-12.json`](census/2026-11-12.json).

| | Count |
|---|---:|
| Documents | 41,092 |
| API entries | 200,084 |
| API aids present | 193,626 |
| **Documents failing a MUST rule** | **4,236 (10.3%)** |

MUST failures, which block reliable indexing:

| Rule | Occurrences | What it looks like |
|---|---:|---|
| M1 provider aid missing | 744 | Document with `name` but no `aid` |
| M1 API aid missing | 6,458 | API entry with no identifier at all |
| M2 grammar | 193 | Trailing hyphens (`…-acl-`), dots (`blockchain.com`), `alice--bob` |
| M3 length | 82 | 100-character agency names; one-character `d`; API aids long enough that YAML folded them across lines |
| M4 prefix ≠ provider | 362 | `abloatai` document listing `ablo:ablo-branches-api` |
| M5 duplicate in document | 65 | The same API aid listed twice |
| M6 aid ≠ directory | 53 | `bamboo/` declares `investbamboo-com`; `cdc/` declares `cdc-gov` |
| M7 provider collision | 21 | Two documents claim one provider aid, usually a duplicate repo (`cdc`/`cdc-gov`, `cerner`/`oracle-health`) |
| M7 API collision | 128 | The same API aid in two providers (`adp` and `automatic-data-processing`; `apigee` and `google-apigee`) |

SHOULD warnings, the naming debt:

| Rule | API aids | Share |
|---|---:|---:|
| A2 trailing `-api` | 181,617 | 93.8% |
| A1 provider repeated in slug | 178,138 | 92.0% |
| A3 artifact word in slug | 706 | 0.4% |
| A4 version in slug | 186 | 0.1% |
| A5 generic slug | 155 | 0.1% |
| P2 provider aid over 40 chars | 141 providers | — |

What this says: the grammar is already the de facto standard. Over 99.8% of the aids that exist parse.
The real gaps are **missing** aids and **ownership** (M1, M4, M7), and those are fixable at the source.
The naming debt (A1/A2) is nearly universal because one generator produced `<provider>:<provider>-<name>-api`
for everything. Under the stability rules it stays as it is and stops being generated.

## Artifacts

- [`aid-json-schema.yml`](aid-json-schema.yml): JSON Schema 2020-12 for the M1–M3 rules on one document.
- [`aid.py`](aid.py): the reference linter (`lint`, `census`) and derivation helpers (`derive <domain>`, `slug <provider> "<API name>"`). Covers every MUST and SHOULD rule, including the cross-field M4–M7 checks that JSON Schema cannot express.
- [`aid-example-1.yml`](aid-example-1.yml): a fully conformant document, with an alias.
- [`aid-example-2.yml`](aid-example-2.yml): a legacy-but-valid document (passes MUST, warns on A1/A2).
- [`tests/bad.yml`](tests/bad.yml): a negative control that breaks every MUST rule.

```bash
pip install pyyaml jsonschema
python3 aid.py lint apis.yml              # exit 1 on any MUST failure
python3 aid.py census path/to/catalog     # summarise a directory of <name>/apis.yml
python3 aid.py derive https://typesafe.ai # -> typesafe-ai
python3 aid.py slug stripe "Stripe Accounts API"   # -> stripe:accounts
```

## Open questions for 0.2

- Should the reserved third segment be defined for versions (`stripe:payment-intents:2024-06-20`) or operations?
- Should `x-aid-aliases` move into the APIs.json core specification as `aliases`?
- Should catalogs publish a resolver (`/aid/{aid}` → canonical URL) as part of conformance?

## License

The specification, schema and examples are [CC BY-NC-SA 4.0](LICENSE). The code (`aid.py`) is
[Apache 2.0](LICENSE-CODE).
