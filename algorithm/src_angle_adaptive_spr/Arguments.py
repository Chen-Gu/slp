
from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.MobilityModel

approaches = ["NO_INTERFERENCE_APPROACH", "ALWAYS_FURTHER_APPORACH", "ALWAYS_CLOSER_APPORACH",
              "ALWAYS_SIDE_APPORACH", "MIN_VALID_APPROACH"]

class Arguments(ArgumentsCommon):
    def __init__(self):
        super(Arguments, self).__init__("SLP Source Angle Adaptive SPR", has_safety_period=True)

        self.add_argument("--source-period", type=float, required=True)
        self.add_argument("--source-mobility",
                          type=simulator.MobilityModel.eval_input,
                          default=simulator.MobilityModel.StationaryMobilityModel())

        self.add_argument("--approach", type=str, choices=approaches, required=True)

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        result.update({
            "APPROACH": self.args.approach,
            self.args.approach: 1,
        })

        return result
