# This file is part of the carrier_send_shipments module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval
import logging

try:
    from mrw.picking import API
except ImportError:
    logger = logging.getLogger(__name__)
    message = 'Install MRW from Pypi: pip install mrw'
    logger.error(message)
    raise Exception(message)

__all__ = ['CarrierApi']
__metaclass__ = PoolMeta


class CarrierApi:
    __name__ = 'carrier.api'
    mrw_franchise = fields.Char('Franchise', states={
            'required': Eval('method') == 'mrw',
            }, help='MRW franchise')
    mrw_subscriber = fields.Char('Subscriber', states={
            'required': Eval('method') == 'mrw',
            }, help='MRW subscriber')
    mrw_department = fields.Char('Department', states={
            'required': Eval('method') == 'mrw',
            }, help='MRW department')

    @classmethod
    def get_carrier_app(cls):
        '''
        Add Carrier MRW APP
        '''
        res = super(CarrierApi, cls).get_carrier_app()
        res.append(('mrw', 'MRW'))
        return res

    def test_mrw(self, api):
        '''
        Test MRW connection
        :param api: obj
        '''
        message = 'Connection unknown result'

        with API(api.username, api.password, api.mrw_franchise, api.mrw_subscriber, api.mrw_department, api.debug) \
                as mrw_api:
            message = mrw_api.test_connection()
        self.raise_user_error(message)
