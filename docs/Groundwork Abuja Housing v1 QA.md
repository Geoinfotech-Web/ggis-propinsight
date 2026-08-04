# Groundwork Abuja Housing v1 - Market Layer QA

## Source and permitted use

- Dataset: Groundwork Data, *Abuja Housing Prices - Groundwork Data v1*
- Version: April 2026
- Source URL: https://huggingface.co/datasets/ayookuns/abuja-housing-prices-v1
- License: CC BY 4.0
- Original size: 481 records (250 rent, 231 sale) across 16 Abuja areas
- Original listing source: PropertyPro.ng, as reported by the dataset publisher

This import uses the CC BY 4.0 dataset release, not automated extraction from
PropertyPro. The records are asking-price listings, not completed transactions.
They must not be represented as verified sale or lease consideration.

## QA run - 2026-08-04

Layer version: `market 2026.08.2`

1. Required-field check passed for all 481 records: price, listing type, area,
   listing ID, listing date, and source URL were present.
2. Listing IDs were unique across all 481 source records.
3. Listing type was restricted to `rent` or `sale`; values were normalised to
   `NGN/year` and `NGN`, respectively.
4. Localities were geocoded with OpenStreetMap Nominatim. Thirteen localities
   resolved unambiguously inside the FCT pilot. Apo, Dawaki, and Karsana were
   rejected because their automated result was ambiguous or absent (95 rows).
5. Prices were checked within each area/listing-type group. Values had to be
   between 0.15x and 6x the group median and within absolute guards of
   NGN 500,000-100,000,000/year for rent or NGN 5,000,000-5,000,000,000 for
   sale. Six outliers were rejected.
6. `last_updated` became the observation date. Three records without that
   field used their valid `date_added` value.
7. Accepted output: 380 records - 201 rent and 179 sale listings.

## Publication semantics

- `sample_type`: `listing`
- `verified`: `false`
- Geocoding precision: locality centroid, not parcel or street coordinate
- Scorecard use: indicative spatial asking-price evidence only
- Listing display: title, area/address, bedrooms, property type, asking price,
  observation date, and original source URL are retained for source review
- Persona routing: tenants see rent listings; home buyers see sale listings
- Required caveat: not a valuation and not evidence of a completed transaction
- Availability caveat: users must confirm current availability, price, and terms
  with the listing source

The dataset can support current price-level and indicative rent-to-sale yield
analysis. Because it is a single April 2026 snapshot, it does not independently
support a historical price trend; that indicator must remain unavailable until
additional licensed snapshots are published.
