# This file is part of the carrier_send_shipments_mrw module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase


class CarrierSendShipmentsMrwTestCase(ModuleTestCase):
    'Test Carrier Send Shipments Mrw module'
    module = 'carrier_send_shipments_mrw'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        CarrierSendShipmentsMrwTestCase))
    return suite