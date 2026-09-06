# Glossary

## Product data and catalog onboarding

| Term | Meaning in this project |
| --- | --- |
| Catalog onboarding / product data onboarding | Turning information in product catalogs and brochures into records that can be reviewed and loaded into business systems. |
| Product Master Data | Relatively stable product identifiers and attributes: product code, model, name, description, category, materials, and specifications. This domain is broader than the current extraction schema. |
| Supplier Item Master Data | The supplier-specific representation of an item, including its source identifier and relationships to commercial and logistics information. Used here as the umbrella for the data being onboarded. |
| Supplier Master Data | Information about the organization supplying an item, such as its identity and contact details. Separate from the product itself. |
| Commercial / Purchasing Data | Quoted unit price, currency, MOQ, purchasing terms, and, where supported, lead time. These describe a purchasing relationship or offer, rather than universal product attributes. |
| Commercial offer | A particular set of quoted prices and purchasing terms for an item. An item can have multiple offers. A quoted price is not necessarily a retail price. |
| Logistics / Packaging Data | Physical and fulfillment information, such as carton dimensions, cubic volume, and quantities at a specified packaging level. |
| SKU | Stock Keeping Unit: a code used to identify an item within a particular organization's catalog. It is not necessarily globally unique. |
| MOQ | Minimum Order Quantity: the smallest quantity specified for an order or offer. Preserve the source's quantity and applicable unit. |
| Lead time | The stated time between a defined ordering milestone and fulfillment. It is a domain concept; the current extraction schema has no dedicated lead-time field. |
| UOM | Unit of Measure, such as centimeters, kilograms, or pieces. Extraction preserves source units; conversions belong in a separate transformation step. |
| CBM | Cubic meters: a measure of cubic volume used in logistics and freight planning. Identify whether the source describes product, carton, or shipment volume. |
| Packaging hierarchy | Packaging levels such as individual unit, inner pack, case/master carton, and pallet or crate. Use only the levels supported by the source; the current schema does not model a complete hierarchy. |

## What does PPV mean here?

**PPV is a project-internal extraction label, not the business name for Product Master Data.** In this repository it appears in names such as `PPVProduct`, `ppv_results`, and `PPV_MAX_OUTPUT_TOKENS`.

The code does not establish an authoritative expansion of the acronym. Read it here as **structured item-data extraction**, covering product identity, commercial offers, and packaging. Documentation uses the business terms above; existing code and configuration names remain unchanged.

Product Master Data describes only one part of that output. For example, a product name belongs to the product master, a quoted unit price belongs to commercial data, and carton volume belongs to logistics data.

## Evidence and data quality

| Term | Meaning |
| --- | --- |
| Extraction | Recovering facts explicitly supported by the source document. Missing prices, MOQ, or logistics values must not be invented. |
| Enrichment | Adding descriptive or merchandising metadata from grounded product information and imagery. The repository's visual enrichment currently uses mock results. |
| Source evidence / provenance | References that let a reviewer trace information to its origin. Current product records can retain a source page and raw text; this is not independently verified evidence for every field. |
| Extraction confidence | A model-reported assessment of certainty. It is a review signal, not proof that a value is correct. |
| Schema validation | Checking whether a record fits the expected fields and data types. It does not establish business approval or factual correctness. |
| Completeness | Whether the required information is present for a particular use. Downstream systems define their own required and optional attributes. |
| Normalization | An explicit transformation into agreed units, codes, or formats. Preserve the original values and keep transformations traceable; the pipeline does not normalize all business data. |
| Application-level human review | People approve, correct, or reject records in your application. The graph returns review statuses; it does not implement a review UI or pause for approval. |

## Systems and implementation

| Term | Role |
| --- | --- |
| PIM | Product Information Management: manages product content and attributes. A custom adapter can create review candidates in your PIM. |
| ERP | Enterprise Resource Planning: supports business operations such as purchasing and inventory. Approved item records can be synchronized through your integration. |
| CRM | Customer Relationship Management: manages customer relationships and related commercial records. Your adapter determines which approved information belongs there. |
| Upsert | Create a record if it does not exist, or update the identified existing record. |
| Idempotent synchronization | Repeating the same synchronization produces the same intended result without creating duplicates. Your integration needs stable external identifiers and retry handling. |
| LangGraph | Orchestrates the repository's processing stages and routing. |
| LLM | Large Language Model: used for structured extraction and optional document classification. |
| VLM | Vision-Language Model: interprets images together with text. Live visual enrichment is not implemented here. |
| Qdrant | Stores document chunk embeddings and evidence metadata for similarity search. |
| RAG | Retrieval-Augmented Generation: retrieves relevant evidence before a model produces an answer. Indexing and a search helper exist here, but extraction currently reads document text directly. |
| Pydantic | Defines and validates the structure of extracted records. |

[Output guide](outputs.md) · [Integration guide](integrations.md) · [Back to the README](../README.md)
