# This file is part of the carrier_send_shipments module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from mrw.picking import Picking
from trytond.modules.carrier_send_shipments.tools import unaccent, unspaces
import logging
import tempfile

__all__ = ['ShipmentOut']
__metaclass__ = PoolMeta


class ShipmentOut:
    __name__ = 'stock.shipment.out'

    @classmethod
    def send_mrw(self, api, shipments):
        '''
        Send shipments out to mrw
        :param api: obj
        :param shipments: list
        Return references, labels, errors
        '''
        pool = Pool()
        CarrierApi = pool.get('carrier.api')

        references = []
        labels = []
        errors = []

        default_service = CarrierApi.get_default_carrier_service(api)

        with Picking(api.username, api.password, api.mrw_franchise, api.mrw_subscriber, api.mrw_department, api.debug) as picking_api:
            for shipment in shipments:
                service = shipment.carrier_service or default_service

                notes = ''
                if shipment.carrier_notes:
                    notes = shipment.carrier_notes

                packages = shipment.number_packages
                if packages == 0:
                    packages = 1

                if shipment.carrier_cashondelivery_total:
                    price_ondelivery = shipment.carrier_cashondelivery_total
                elif shipment.carrier_sale_price_total:
                    price_ondelivery = shipment.carrier_sale_price_total
                else:
                    price_ondelivery = shipment.total_amount

                data = {}
                #~ data['codigo_direccion'] = ''
                #~ data['codigo_via'] = ''
                data['via'] = unaccent(shipment.delivery_address.street)
                #~ data['numero'] = ''
                #~ data['resto'] = ''
                data['codigo_postal'] = shipment.delivery_address.zip
                data['poblacion'] = unaccent(shipment.delivery_address.city)
                #~ data['provincia'] = ''
                data['nif'] = shipment.customer.vat_number
                data['nombre'] = unaccent(shipment.customer.name)
                data['telefono'] = unspaces(shipment.delivery_address.phone or shipment.company.party.phone)
                data['contacto'] = unaccent(shipment.delivery_address.name
                        or shipment.customer.name)
                data['atencion_de'] = unaccent((shipment.delivery_address.name
                        or shipment.customer.name))
                data['observaciones'] = unaccent(notes)
                #~ data['fecha'] = ''
                data['referencia'] = shipment.code
                data['codigo_servicio'] = str(service.code)
                data['bultos'] = packages
                #~ data['peso'] = ''
                if shipment.carrier_cashondelivery:
                    if not price_ondelivery:
                        message = 'Shipment %s not have price and send ' \
                                'cashondelivery' % (shipment.code)
                        errors.append(message)
                        continue
                    data['reembolso'] = 'O'
                    data['importe_reembolso'] = str(price_ondelivery).replace(".", ",")

                # Send shipment data to carrier
                reference, error = picking_api.create(data)

                if reference:
                    self.write([shipment], {
                        'carrier_tracking_ref': reference,
                        'carrier_service': service,
                        'carrier_delivery': True,
                        })
                    logging.getLogger('mrw').info(
                        'Send shipment %s' % (shipment.code))
                    references.append(shipment.code)
                else:
                    logging.getLogger('mrw').error(
                        'Not send shipment %s.' % (shipment.code))

                if error:
                    logging.getLogger('mrw').error(
                        'Not send shipment %s. %s' % (shipment.code, error))
                    errors.append(shipment.code)

                labels += self.print_labels_mrw(api, shipments)

        return references, labels, errors

    @classmethod
    def print_labels_mrw(cls, api, shipments):
        '''
        Get labels from shipments out from MRW
        '''
        labels = []
        dbname = Transaction().cursor.dbname

        with Picking(api.username, api.password, api.mrw_franchise, api.mrw_subscriber, api.mrw_department, api.debug) as picking_api:
            for shipment in shipments:
                if not shipment.carrier_tracking_ref:
                    logging.getLogger('mrw').error(
                        'Shipment %s has not been sent by MRW.'
                        % (shipment.code))
                    continue

                reference = shipment.carrier_tracking_ref

                data = {}
                data['numero'] = reference

                label = picking_api.label(data)
                if not label:
                    logging.getLogger('mrw').error(
                        'Label for shipment %s is not available from MRW.'
                        % shipment.code)
                    continue
                with tempfile.NamedTemporaryFile(
                        prefix='%s-mrw-%s-' % (dbname, reference),
                        suffix='.pdf', delete=False) as temp:
                    temp.write(label) # Envialia PDF file
                logging.getLogger('mrw').info(
                    'Generated tmp label %s' % (temp.name))
                temp.close()
                labels.append(temp.name)
            cls.write(shipments, {'carrier_printed': True})

            return labels
