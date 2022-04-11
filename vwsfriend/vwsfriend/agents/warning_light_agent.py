import logging
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError

from vwsfriend.model.warning_light import WarningLight

from weconnect.addressable import AddressableLeaf

LOG = logging.getLogger("VWsFriend")


class WarningLightAgent():
    def __init__(self, session, vehicle):
        self.session = session
        self.vehicle = vehicle
        self.enabledLights = session.query(WarningLight).filter(and_(WarningLight.vehicle == vehicle,
                                                                     WarningLight.end.is_(None))).order_by(WarningLight.start.desc()).all()

        # register for updates:
        if self.vehicle.weConnectVehicle is not None:
            if self.vehicle.weConnectVehicle.statusExists('vehicleHealthWarnings', 'warningLights') \
                    and self.vehicle.weConnectVehicle.domains['vehicleHealthWarnings']['warningLights'].enabled:
                self.vehicle.weConnectVehicle.domains['vehicleHealthWarnings']['warningLights'].carCapturedTimestamp.addObserver(
                    self.__onCarCapturedTimestampChange, AddressableLeaf.ObserverEvent.VALUE_CHANGED, onUpdateComplete=True)
                self.__onCarCapturedTimestampChange(self.vehicle.weConnectVehicle.domains['vehicleHealthWarnings']['warningLights'].carCapturedTimestamp, None)

    def __onCarCapturedTimestampChange(self, element, flags):  # noqa: C901
        if element is not None and element.value is not None:
            warningLightsStatus = self.vehicle.weConnectVehicle.domains['vehicleHealthWarnings']['warningLights']
            for warningLight in warningLightsStatus.warningLights.values():
                if warningLight.messageId.value not in [light.messageId for light in self.enabledLights]:
                    warningLightEntry = WarningLight(self.vehicle, warningLight.messageId.value, element.value, warningLight.text.value,
                                                     warningLight.category.value)

                    if warningLightsStatus.mileage_km.enabled:
                        warningLightEntry.start_mileage = warningLightsStatus.mileage_km.value
                    if warningLight.serviceLead.enabled:
                        warningLightEntry.serviceLead = warningLight.serviceLead.value
                    if warningLight.customerRelevance.enabled:
                        warningLightEntry.customerRelevance = warningLight.customerRelevance.value

                    try:
                        with self.session.begin_nested():
                            self.session.add(warningLightEntry)
                        self.session.commit()
                    except IntegrityError as err:
                        LOG.warning('Could not add warning light entry to the database, this is usually due to an error in the WeConnect API (%s)', err)
            for enabledLight in self.enabledLights:
                if enabledLight.messageId not in warningLightsStatus.warningLights:
                    enabledLight.end = element.value

                    if warningLightsStatus.mileage_km.enabled:
                        enabledLight.end_mileage = warningLightsStatus.mileage_km.value

            self.enabledLights = self.session.query(WarningLight).filter(and_(WarningLight.vehicle == self.vehicle,
                                                                              WarningLight.end.is_(None))).order_by(WarningLight.start.desc()).all()

    def commit(self):
        pass