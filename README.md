# Marketing campaign performance (GA360 sample)

> Work in progress. Headline recommendation, chart and dashboard link land in the final phase.

End-to-end campaign performance analysis of 12 months of Google Analytics 360 sample data
(Aug 2016 to Aug 2017, BigQuery public dataset): funnel by acquiring channel, CAC and ROI
under stated spend assumptions, 30/60/90-day retention, and a one-page cut/scale memo.

## Why this dataset
The GA360 sample has `channelGrouping`, `trafficSource.source / medium / campaign`, a persistent
`fullVisitorId`, revenue, and 12 months of history. The REES46 e-commerce dataset (Kaggle) was
considered and rejected: it has no traffic source, channel or campaign column, so it cannot say
which channel acquired a user.

## How to run
```
make all        # analyze + report + test from committed parquet (no GCP needed)
make extract    # rerun BigQuery extraction (needs gcloud ADC + billing project)
```

See [CLAUDE.md](CLAUDE.md) for definitions and [config/assumptions.yaml](config/assumptions.yaml)
for every assumption.

License: MIT.
