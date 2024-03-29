# This file is part of carrier_send_shipments_mrw module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.i18n import gettext
from trytond.exceptions import UserError


class CarrierManifest(metaclass=PoolMeta):
    __name__ = 'carrier.manifest'

    def get_manifest_mrw(self, api, from_date, to_date):
        raise UserError(
            gettext('carrier_send_shipments_mrw.msg_mrw_not_manifest'))
