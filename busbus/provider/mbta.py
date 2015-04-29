from busbus.provider import ProviderBase
from busbus.provider.gtfs import GTFSMixin


class MBTAProvider(GTFSMixin, ProviderBase):
    """
    Provides data from the MBTA-realtime API v2 and the MBTA GTFS feed.

    http://realtime.mbta.com/

    An API key is required to access the MBTA-realtime API. MBTA provides a key
    you can use for development at:
        http://realtime.mbta.com/Portal/Content/Download/APIKey.txt
    This key is for development only -- MBTA requests you do not use this key
    in production; request a key instead.
    """

    legal = [
        ('http://www.massdot.state.ma.us/Portals/0/docs/developers/'
         'RelationshipPrinciples.pdf'),
        ('http://www.massdot.state.ma.us/Portals/0/docs/developers/'
         'develop_license_agree.pdf'),
    ]
    credit = 'MassDOT'
    credit_url = 'http://www.massdot.state.ma.us'
    country = 'US'

    # Lowering this number may cause you to be suspended from the data feed
    # (API docs, "Use of MBTA data"). This number is in seconds. The actual
    # value required by the MBTA is 10 seconds.
    poll_interval = 12

    gtfs_url = "http://www.mbta.com/uploadedfiles/MBTA_GTFS.zip"

    def __init__(self, mbta_api_key, engine=None):
        super(MBTAProvider, self).__init__(engine, self.gtfs_url)
        self.mbta_api_key = mbta_api_key
