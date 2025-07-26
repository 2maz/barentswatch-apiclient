# Barentswatch API Client

The script in this repository allows to collect AIS messages send via the barentswatch REST API for AIS data.

## Installation

Create an account and register a client (see http://developer.barentswatch.no/docs/appreg).

Fill in the details, i.e. BARENTS_WATCH_CLIENT_ID and BARENTS_WATCH_CLIENT_SECRET in barents-watch.token.sh.

```
source barents-watch.token.sh

python3 -m venv venv-barents-watch
. venv-barents-watch/bin/activate

pip install requests
``` 

## Usage
To download the data into daily CSV files of the format AIS_YYYY_mm_dd.csv

``` 
python barents-watch.download.py
```

## License
This work is licensed under the [BSD-3-Clause License](https://github.com/2maz/ai4copsec-barentswatch/blob/main/LICENSE).
Data is made accessible via barentswatch.no and licensed under [Norwegian License for Public Data](https://data.norge.no/nlod) (see also https://www.barentswatch.no/artikler/api-vilkar/).

## Copyright

Copyright (c) 2025 [Simula Research Laboratory, Oslo, Norway](https://www.simula.no/research/research-departments)

## Acknowledgments

All data is provided by the live AIS API from [barentswatch.no](https://developer.barentswatch.no/docs/AIS/live-ais-api/).

The development of this client is part of the EU-project [AI4COPSEC](https://ai4copsec.eu) which receives funding
 from the Horizon Europe framework programme under Grant Agreement N. 101190021.

