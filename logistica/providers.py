# Alliance Auth
from esi.openapi_clients import ESIClientProvider

from . import __version__ as version

esi = ESIClientProvider(
    compatibility_date="2026-07-21",
    ua_appname="aa-logistica",
    ua_url="github.com/leesolway/aa-logistica",
    ua_version=version,
    operations=[
        "GetUniverseStructuresStructureId",
    ],
)
