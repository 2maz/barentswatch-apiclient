# You need to register an account with barentswatch.no
#
# BARENTS_WATCH_CLIENT_ID=your_user
# BARENTS_WATCH_CLIENT_SECRET=your_secret

export BARENTS_WATCH_CLIENT_ID
export BARENTS_WATCH_CLIENT_SECRET

BARENTS_WATCH_ACCESS_TOKEN=$(curl -X POST https://id.barentswatch.no/connect/token \
-H 'Content-Type: application/x-www-form-urlencoded' \
--data-urlencode "client_id=$BARENTS_WATCH_CLIENT_ID" \
--data-urlencode "client_secret=$BARENTS_WATCH_CLIENT_SECRET" \
--data-urlencode 'scope=ais' \
--data-urlencode 'grant_type=client_credentials' | \
python3 -m json.tool | grep "access_token" | awk -F\" '{print $4}')

export BARENTS_WATCH_ACCESS_TOKEN
echo $BARENTS_WATCH_ACCESS_TOKEN

# Streaming request
#curl --location --request GET 'https://live.ais.barentswatch.no/v1/latest/combined' \
#    --header "Authorization: Bearer $BARENTS_WATCH_ACCESS_TOKEN"

