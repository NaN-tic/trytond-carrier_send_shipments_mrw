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
    def __setup__(cls):
        super(ShipmentOut, cls).__setup__()
        cls._error_messages.update({
            'mrw_add_services': 'Select a service or default service in MRW API',
            'mrw_not_price': 'Shipment "%(name)s" not have price and send '
                'cashondelivery',
            'mrw_not_send': 'Not send shipment %(name)s',
            'mrw_not_send_error': 'Not send shipment %(name)s. %(error)s',
            'mrw_not_label': 'Not available "%(name)s" label from MRW',
            })

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
        ShipmentOut = pool.get('stock.shipment.out')

        references = []
        labels = []
        errors = []

        default_service = CarrierApi.get_default_carrier_service(api)

        with Picking(api.username, api.password, api.mrw_franchise, api.mrw_subscriber, api.mrw_department, api.debug) as picking_api:
            for shipment in shipments:
                service = shipment.carrier_service or shipment.carrier.service or default_service
                if not service:
                    message = self.raise_user_error('mrw_add_services', {},
                        raise_exception=False)
                    errors.append(message)
                    continue

                notes = ''
                if shipment.carrier_notes:
                    notes = shipment.carrier_notes

                packages = shipment.number_packages
                if not packages or packages == 0:
                    packages = 1

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
                data['telefono'] = unspaces(ShipmentOut.get_phone_shipment_out(shipment))
                data['contacto'] = unaccent(shipment.delivery_address.name
                        or shipment.customer.name)
                data['atencion_de'] = unaccent((shipment.delivery_address.name
                        or shipment.customer.name))
                data['observaciones'] = unaccent(notes)
                #~ data['fecha'] = ''
                data['referencia'] = shipment.code
                data['codigo_servicio'] = str(service.code)
                data['bultos'] = packages
                if api.weight and hasattr(shipment, 'weight_func'):
                    weight = str(int(round(shipment.weight_func)))
                    if weight == '0':
                        weight = '1'
                    data['peso'] = weight
                if shipment.carrier_cashondelivery:
                    price_ondelivery = ShipmentOut.get_price_ondelivery_shipment_out(shipment)
                    if not price_ondelivery:
                        message = self.raise_user_error('mrw_not_price', {
                                'name': shipment.rec_name,
                                }, raise_exception=False)
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
                        'carrier_send_date': ShipmentOut.get_carrier_date(),
                        'carrier_send_employee': ShipmentOut.get_carrier_employee() or None,
                        })
                    logging.getLogger('mrw').info(
                        'Send shipment %s' % (shipment.code))
                    references.append(shipment.code)
                else:
                    logging.getLogger('mrw').error(
                        'Not send shipment %s.' % (shipment.code))

                if error:
                    message = self.raise_user_error('mrw_not_send_error', {
                            'name': shipment.rec_name,
                            'error': error,
                            }, raise_exception=False)
                    logging.getLogger('mrw').error(message)
                    errors.append(message)

                labels += self.print_labels_mrw(api, shipments)

        return references, labels, errors

    @classmethod
    def print_labels_mrw(self, api, shipments):
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
            self.write(shipments, {'carrier_printed': True})

            return labels
