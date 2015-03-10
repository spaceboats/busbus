from busbus.provider import ProviderBase
from busbus.provider.gtfs import GTFSMixin


class LawrenceTransitProvider(GTFSMixin, ProviderBase):
    gtfs_url = ("http://lawrenceks.org/assets/gis/google-transit/"
                "google_transit.zip")

    def __init__(self, engine=None):
        super(LawrenceTransitProvider, self).__init__(engine, self.gtfs_url)
