from busbus.provider import ProviderBase
from busbus.provider.gtfs import GTFSMixin


class CTranProvider(GTFSMixin, ProviderBase):
    credit = 'C-TRAN'
    credit_url = 'http://www.c-tran.org/'
    country = 'US'

    gtfs_url = "http://www.c-tran.com/images/Google/GoogleTransitUpload.zip"

    def __init__(self, engine=None):
        super(CTranProvider, self).__init__(engine, self.gtfs_url)
