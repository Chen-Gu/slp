
from __future__ import print_function, division

import numpy as np

from simulator.MetricsCommon import MetricsCommon, DutyCycleMetricsCommon

class Metrics(DutyCycleMetricsCommon):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d["AwaySent"]               = lambda x: x.number_sent("Away")
        d["BeaconSent"]             = lambda x: x.number_sent("Beacon")

        d.update(DutyCycleMetricsCommon.items())

        return d
