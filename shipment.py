# This file is part of the carrier_send_shipments module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.i18n import gettext
from trytond.exceptions import UserError
from mrw.picking import Picking
from trytond.modules.carrier_send_shipments.tools import unaccent, unspaces
import logging
import tempfile

__all__ = ['ShipmentOut']

logger = logging.getLogger(__name__)


class ShipmentOut(metaclass=PoolMeta):
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
        ShipmentOut = pool.get('stock.shipment.out')
        Uom = pool.get('product.uom')
        Date = pool.get('ir.date')

        references = []
        labels = []
        errors = []

        default_service = CarrierApi.get_default_carrier_service(api)
        for shipment in shipments:
            if not shipment.customer_phone_numbers:
                raise UserError(
                    gettext('carrier_send_shipments_mrw.msg_no_customer_phone',
                         name=shipment.number))
        with Picking(api.username, api.password, api.mrw_franchise, api.mrw_subscriber,
                api.mrw_department, timeout=api.timeout, debug=api.debug) as picking_api:
            for shipment in shipments:
                service = shipment.carrier_service or shipment.carrier.service or default_service
                if not service:
                    message = gettext('carrier_send_shipments_mrw.msg_mrw_add_services')
                    errors.append(message)
                    continue

                if api.reference_origin and hasattr(shipment, 'origin'):
                    code = shipment.origin and shipment.origin.rec_name or shipment.number
                else:
                    code = shipment.number

                notes = ''
                if shipment.carrier_notes:
                    notes = '%s\n' % shipment.carrier_notes

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
                data['nif'] = shipment.customer.identifier_code
                data['nombre'] = unaccent(shipment.customer.name)
                data['telefono'] = unspaces(shipment.customer_phone_numbers)
                data['contacto'] = unaccent(shipment.delivery_address.name
                        or shipment.customer.name)
                data['atencion_de'] = unaccent((shipment.delivery_address.name
                        or shipment.customer.name))
                data['observaciones'] = unaccent(notes)
                data['fecha'] = Date.today().strftime("%d/%m/%Y")
                data['referencia'] = code
                data['codigo_servicio'] = str(service.code)
                data['bultos'] = packages

                if api.weight and hasattr(shipment, 'weight_func'):
                    weight = shipment.weight_func
                    weight = 1 if weight == 0.0 else weight

                    if api.weight_api_unit:
                        if shipment.weight_uom:
                            weight = Uom.compute_qty(
                                shipment.weight_uom, weight, api.weight_api_unit)
                        elif api.weight_unit:
                            weight = Uom.compute_qty(
                                api.weight_unit, weight, api.weight_api_unit)

                    # weight is integer value, not float
                    weight = int(round(weight))
                    weight = 1 if weight == 0 else weight
                    data['peso'] = str(weight)

                if shipment.carrier_cashondelivery:
                    price_ondelivery = shipment.carrier_cashondelivery_price
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
                    logger.info('Send shipment %s' % (shipment.number))
                    references.append(shipment.number)
                else:
                    logger.error('Not send shipment %s.' % (shipment.number))

                if error:
                    message = gettext('carrier_send_shipments_mrw.msg_mrw_not_send_error',
                        name=shipment.rec_name,
                        error=error)
                    logger.error(message)
                    errors.append(message)

                labels += self.print_labels_mrw(api, [shipment])

        return references, labels, errors

    @classmethod
    def print_labels_mrw(self, api, shipments):
        '''
        Get labels from shipments out from MRW
        '''
        labels = []
        dbname = Transaction().database.name

        with Picking(api.username, api.password, api.mrw_franchise, api.mrw_subscriber,
                api.mrw_department, timeout=api.timeout, debug=api.debug) as picking_api:
            for shipment in shipments:
                if not shipment.carrier_tracking_ref:
                    logger.error(
                        'Shipment %s has not been sent by MRW.'
                        % (shipment.number))
                    continue

                reference = shipment.carrier_tracking_ref

                data = {}
                data['numero'] = reference

                label = picking_api.label(data)
                if not label:
                    logger.error(
                        'Label for shipment %s is not available from MRW.'
                        % shipment.number)
                    continue
                with tempfile.NamedTemporaryFile(
                        prefix='%s-mrw-%s-' % (dbname, reference),
                        suffix='.pdf', delete=False) as temp:
                    temp.write(label) # Envialia PDF file
                logger.info(
                    'Generated tmp label %s' % (temp.name))
                temp.close()
                labels.append(temp.name)
            self.write(shipments, {'carrier_printed': True})

        return labels

    @classmethod
    def get_labels_mrw(self, api, shipments):
        '''
        Get labels from shipments out from MRW
        '''
        shipment, = shipments
        if not shipment.carrier_tracking_ref:
            raise UserError(
                gettext('carrier_send_shipments_mrw.msg_no_carrier_ref'))
        with Picking(api.username, api.password, api.mrw_franchise,
                api.mrw_subscriber, api.mrw_department, timeout=api.timeout,
                debug=api.debug) as picking_api:
            reference = shipment.carrier_tracking_ref
            data = {}
            data['numero'] = reference
            label = picking_api.label(data)
            if not label:
                logger.error(
                    'Label for shipment %s is not available from MRW.'
                    % shipment.number)
            return label
