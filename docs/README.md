# bwac - barentswatch API Client

The script in this repository allows to collect AIS messages send via the barentswatch REST API for AIS data.

## Installation

Install from source:

```
git clone https://github.com/2maz/barentswatch-apiclient.git

python3 -m venv venv-barents-watch
. venv-barents-watch/bin/activate

pip install ./barentswatch-apiclient
```

## Usage

Create an account and register a client (see http://developer.barentswatch.no/docs/appreg).
Create a .env file with the credentials for accessing the

```
BARENTS_WATCH_CLIENT_ID=your@email.com:yourapp
BARENTS_WATCH_CLIENT_SECRET=XXXXX
```

To download data from the livestream by creating daily CSV files of the format AIS_YYYY_mm_dd.csv use

```
$> bwac live
```

To retrieve data from the historic api for a specific timeframe, which can be a maximum of 14 days in the past (this limit is set by barentswatch):

```
$> bwac historic --from-date 2026-04-14T00:00:00+00:00 --to-date 2026-04-15T23:59:59+00:00

```

## License
This work is licensed under the [BSD-3-Clause License](https://github.com/2maz/ai4copsec-barentswatch/blob/main/LICENSE).
Data is made accessible via barentswatch.no and licensed under [Norwegian License for Public Data](https://data.norge.no/nlod) (see also https://www.barentswatch.no/artikler/api-vilkar/).

## Copyright

Copyright (c) 2025-2026 [Simula Research Laboratory, Oslo, Norway](https://www.simula.no/research/research-departments)

## Acknowledgments

All data is provided by the live AIS API from [barentswatch.no](https://developer.barentswatch.no/docs/AIS/live-ais-api/).

The development of this client is part of the EU-project [AI4COPSEC](https://ai4copsec.eu) which receives funding
 from the Horizon Europe framework programme under Grant Agreement N. 101190021.
