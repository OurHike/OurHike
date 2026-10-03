"""Every active NWS alert in the US, as `raw_nws__alerts`, on the hourly lane that builds `warnings`.

NWS alerts are public domain by the weather.gov disclaimer (features/WEATHER.md
§9), and the bake credits "National Weather Service" (export_weather_alerts.py's
CREDIT). What reaches a phone is decided downstream: staging keeps NWS's
`Actual` messages and drops cancellations (WN01), and the bake places each
alert on the trail squares it reaches. Neither filter happens here.

The conditions job owns `warnings`, so NWS moves there from the weather job's
`:55` run (decision 28a). It rides the hourly lane for now. Splitting it into
its own `nws` pipeline, so that the production and UA legs do not each ask NWS,
is stage 4's job wiring (ELT.md, "The hourly lanes").
"""

from extract._kinds import nws_alerts

TYPE = "warnings"
UNREGISTERED = 'a non-registry input: lib/nws_alerts.py\'s ALERTS_URL is its one home (ELT.md, "What moves")'
RESOURCES = [nws_alerts()]
