
import argparse

from simulator.Simulation import Simulation
import simulator.Attacker as Attacker
import simulator.Configuration as Configuration
import simulator.SourcePeriodModel as SourcePeriodModel

# Inheritance diagram for different modes:
# TESTBED < SINGLE < PARALLEL < CLUSTER
#                  < GUI

# OFFLINE < OFFLINE_GUI

def _secure_random():
    """Returns a random 32 bit (4 byte) signed integer"""
    import struct, os
    return struct.unpack("<i", os.urandom(4))[0]

class ArgumentsCommon(object):
    def __init__(self, description, has_safety_period=False):
        parser = argparse.ArgumentParser(description=description, add_help=False)

        subparsers = parser.add_subparsers(title="mode", dest="mode")

        ###

        parser_testbed = subparsers.add_parser("TESTBED", add_help=True)

        parser_testbed.add_argument("-c", "--configuration", type=str, required=True, choices=Configuration.names())

        parser_testbed.add_argument("-v", "--verbose", action="store_true")

        ###

        parser_single = subparsers.add_parser("SINGLE", add_help=False, parents=[parser_testbed])

        parser_single.add_argument("--seed", type=int, required=False)

        parser_single.add_argument("-cm", "--communication-model", type=str, choices=Simulation.available_communication_models(), required=True)
        parser_single.add_argument("-nm", "--noise-model", type=str, choices=Simulation.available_noise_models(), required=True)

        parser_single.add_argument("-ns", "--network-size", type=int, required=True)
        parser_single.add_argument("-d", "--distance", type=float, default=4.5)

        parser_single.add_argument("-am", "--attacker-model", type=Attacker.eval_input, required=True)

        parser_single.add_argument("-st", "--latest-node-start-time", type=float, required=False, default=1.0,
                                   help="Used to specify the latest possible start time in seconds. Start times will be chosen in the inclusive random range [0, x] where x is the value specified.")

        parser_single.add_argument("--node-id-order", choices=["topology", "randomised"], default="randomised")

        if has_safety_period:
            parser_single.add_argument("-safety", "--safety-period", type=float, required=True)

        ###

        parser_gui = subparsers.add_parser("GUI", add_help=False, parents=[parser_single])

        parser_gui.add_argument("--gui-node-label", type=str, required=False, default=None)
        parser_gui.add_argument("--gui-scale", type=int, required=False, default=6)

        ###

        parser_parallel = subparsers.add_parser("PARALLEL", add_help=False, parents=[parser_single])

        parser_parallel.add_argument("--job-size", type=int, required=True)
        parser_parallel.add_argument("--thread-count", type=int, default=None)

        ###

        parser_cluster = subparsers.add_parser("CLUSTER", add_help=False, parents=[parser_parallel])

        parser_cluster.add_argument("--job-id", type=int, default=None,
                                    help="Used to pass the array id when this job has been submitted as a job array to the cluster.")

        ###
        ###

        parser_offline = subparsers.add_parser("OFFLINE", add_help=False)

        parser_offline.add_argument("--merged-log", type=str, required=True)

        parser_offline.add_argument("-am", "--attacker-model", type=Attacker.eval_input, required=True)
        parser_offline.add_argument("-c", "--configuration", type=str, required=True, choices=Configuration.names())
        
        if has_safety_period:
            parser_offline.add_argument("-safety", "--safety-period", type=float, required=True)

        parser_offline.add_argument("--seed", type=int, required=False)

        ###

        parser_offline_gui = subparsers.add_parser("OFFLINE_GUI", add_help=False, parents=[parser_offline])

        parser_offline_gui.add_argument("--gui-scale", type=int, required=False, default=6)

        ###
        ###

        # Store any of the parsers that we need
        self._parser = parser
        self._online_subparsers = (parser_testbed, parser_single, parser_gui, parser_parallel, parser_cluster)
        self._offline_subparsers = (parser_offline, parser_offline_gui)

        # Haven't parsed anything yet
        self.args = None

        # Don't show these arguments when printing the argument values before showing the results
        self.arguments_to_hide = {"job_id", "verbose", "gui_node_label", "gui_scale", "mode", "seed"}

    def add_argument(self, *args, **kwargs):

        # TODO: Work out a way to just add this to a single subparser and let the argument
        # trickle down to the other subparsers.

        for parser in self._online_subparsers:
            parser.add_argument(*args, **kwargs)

    def parse(self, argv):
        self.args = self._parser.parse_args(argv)

        if hasattr(self.args, 'seed'):
            if self.args.seed is None:
                self.args.seed = _secure_random()

        if hasattr(self.args, 'source_mobility'):
            configuration = Configuration.create(self.args.configuration, self.args)
            self.args.source_mobility.setup(configuration)
        
        return self.args

    def build_arguments(self):
        result = {}

        if self.args.verbose:
            result["SLP_VERBOSE_DEBUG"] = 1

        # Source period could either be a float or a class derived from PeriodModel
        if hasattr(self.args, 'source_period'):
            if isinstance(self.args.source_period, float):
                if float(self.args.source_period) <= 0:
                    raise RuntimeError("The source_period ({}) needs to be greater than 0".format(self.args.source_period))

                result["SOURCE_PERIOD_MS"] = int(self.args.source_period * 1000)
            elif isinstance(self.args.source_period, SourcePeriodModel.PeriodModel):
                result.update(self.args.source_period.build_arguments())
            else:
                raise RuntimeError("The source_period ({}) either needs to be a float or an instance of SourcePeriodModel.PeriodModel".format(self.args.source_period))

        if hasattr(self.args, 'source_mobility'):
            result.update(self.args.source_mobility.build_arguments())
        else:
            # If there are no mobility models provided, then the only source specified
            # by the configuration can be used instead.
            # This is mainly for legacy algorithm support, StationaryMobilityModels
            # are a better choice for new algorithms.

            configuration = Configuration.create(self.args.configuration, self.args)

            if len(configuration.source_ids) != 1:
                raise RuntimeError("Invalid number of source ids in configuration {}, there must be exactly one.".format(configuration))

            (source_id,) = configuration.source_ids

            result["SOURCE_NODE_ID"] = source_id

        return result
