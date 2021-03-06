
import argparse
from random import SystemRandom

import algorithm

from simulator import CommunicationModel, NoiseModel
import simulator.AttackerConfiguration as AttackerConfiguration
import simulator.Configuration as Configuration
import simulator.SourcePeriodModel as SourcePeriodModel
import simulator.FaultModel as FaultModel
import simulator.MetricsCommon as MetricsCommon
import simulator.sim

from data import submodule_loader

def _secure_random():
    """Returns a random 32 bit (4 byte) signed integer"""
    # From: https://stackoverflow.com/questions/9216344/read-32-bit-signed-value-from-an-unsigned-bytestream
    rno = SystemRandom().getrandbits(32)

    if rno >> 31: # is the sign bit set?
        return -0x80000000 + (rno & 0x7fffffff) # "cast" it to signed

    return rno

def _add_safety_period(parser, has_safety_period=False, has_safety_factor=False, **kwargs):
    assert not has_safety_factor or has_safety_period


    if has_safety_period:
        parser.add_argument("-safety", "--safety-period",
                            type=ArgumentsCommon.type_positive_float,
                            required=True)

        if has_safety_factor:
            parser.add_argument("--safety-factor",
                                type=ArgumentsCommon.type_positive_float,
                                required=False,
                                default=1.0)

def _add_low_power_listening(parser, lpl_parameters_mandatory=False, **kwargs):
    parser.add_argument("-lpl", "--low-power-listening", choices=("enabled", "disabled"), default="disabled",
                        help="Enables or disables low power listening. By default LPL is disabled and the radio will always be on.")

    parser.add_argument("--lpl-custom", type=str, default=None,
                        help="The custom module that will be used to provide LPL.")

    if lpl_parameters_mandatory:
        lpl_kwargs = {"required": True}
    else:
        lpl_kwargs = {"default": None}

    parser.add_argument("--lpl-local-wakeup", type=ArgumentsCommon.type_positive_int,
                        help="This is the period for which a node will turn the radio off.", **lpl_kwargs)

    parser.add_argument("--lpl-remote-wakeup", type=ArgumentsCommon.type_positive_int,
                        help="This is a global setting, that configures the period a messages is retransmitted over after being sent.", **lpl_kwargs)

    parser.add_argument("--lpl-delay-after-receive", type=ArgumentsCommon.type_positive_int,
                        help="How long should the radio be kept on after a message is received.", **lpl_kwargs)

    parser.add_argument("--lpl-max-cca-checks", type=ArgumentsCommon.type_positive_int,
                        help="The maximum number of CCA checks performed on each wakeup.", **lpl_kwargs)

    parser.add_argument("--lpl-min-samples-before-detect", "-lpl-msbd", type=ArgumentsCommon.type_positive_int, default=None,
                        help="The minimum number of samples before a signal is considered detected.")

def _add_avrora_radio_model(parser, **kwargs):
    import simulator.AvroraRadioModel as AvroraRadioModel

    parser.add_argument("-rm", "--radio-model",
                        type=AvroraRadioModel.eval_input,
                        choices=AvroraRadioModel.available_models(),
                        required=True)

    parser.add_argument("--max-buffer-size",
                        type=ArgumentsCommon.type_positive_int,
                        default=255)

def _add_cooja_radio_model(parser, **kwargs):
    import simulator.CoojaRadioModel as CoojaRadioModel
    import simulator.CoojaPlatform as CoojaPlatform

    parser.add_argument("-rm", "--radio-model",
                        type=CoojaRadioModel.eval_input,
                        choices=CoojaRadioModel.available_models(),
                        required=True)

    parser.add_argument("-p", "--platform",
                        type=CoojaPlatform.eval_input,
                        choices=CoojaPlatform.available_models(),
                        required=True)

    # COOJA doesn't like debug strings longer than 256 bytes
    # Anything longer than this will get "..." appended.
    # If you need more look at MspDebugOutput.java in Cooja
    parser.add_argument("--max-buffer-size",
                        type=ArgumentsCommon.type_positive_int,
                        default=255)


def _add_log_converter(parser, **kwargs):
    import simulator.OfflineLogConverter as OfflineLogConverter

    parser.add_argument("--log-converter", type=str, choices=OfflineLogConverter.names(), required=True)

def _add_cc2420(parser, **kwargs):
    # See http://www.ti.com/lit/ds/symlink/cc2420.pdf section 28
    # This is for chips with a CC2420 only
    # TOSSIM DOES NOT SIMULATE THIS!
    parser.add_argument("--rf-power",
                        type=int,
                        choices=[3, 7, 11, 15, 19, 23, 27, 31],
                        default=31,
                        help="Used to set the power levels for the CC2420 radio chip. 3 is low, 31 is high. Default: 31")

    # See http://www.ti.com/lit/ds/symlink/cc2420.pdf section 26
    parser.add_argument("--channel",
                        type=int,
                        choices=list(range(11, 27)), # Channels 11 - 26 inclusive
                        default=26,
                        help="The IEEE 802.15.4 rf channel the CC2420 radio chip broadcasts on within the 2.4GHz band. Default: 26")

    parser.add_argument("--acks",
                        choices=["none", "software", "hardware"],
                        default="software",
                        help="CC2420 packet ack strategy. Default: software")

    parser.add_argument("--address-recognition",
                        choices=["none", "software", "hardware"],
                        default="software",
                        help="CC2420 address recognition strategy. Default: software")

OPTS = {
    "configuration":       lambda x, **kwargs: x.add_argument("-c", "--configuration",
                                                              type=str,
                                                              required=True),
                                                              #choices=Configuration.names()),

    "verbose":             lambda x, **kwargs: x.add_argument("-v", "--verbose",
                                                              action="store_true"),

    "low verbose":         lambda x, **kwargs: x.add_argument("-v1", "--low-verbose",
                                                              action="store_true"),

    "debug":               lambda x, **kwargs: x.add_argument("--debug",
                                                              action="store_true"),

    "seed":                lambda x, **kwargs: x.add_argument("--seed",
                                                              type=int,
                                                              required=False,
                                                              help="The random seed provided to the simulator's PRNG"),

    "network size":        lambda x, **kwargs: x.add_argument("-ns", "--network-size",
                                                              type=ArgumentsCommon.type_positive_int,
                                                              required=True,
                                                              help="How large the network should be. Typically causes the network to contain NETWORK_SIZE^2 nodes."),

    "distance":            lambda x, **kwargs: x.add_argument("-d", "--distance",
                                                              type=ArgumentsCommon.type_positive_float,
                                                              default=4.5,
                                                              help="The distance between nodes. How this is used depends on the configuration specified."),

    "node id order":       lambda x, **kwargs: x.add_argument("-nido", "--node-id-order",
                                                              choices=("topology", "randomised"),
                                                              default="topology",
                                                              help="With 'topology' node id orders are the same as the topology defines. 'randomised' causes the node ids to be randomised."),

    "safety period":       _add_safety_period,


    "communication model": lambda x, **kwargs: x.add_argument("-cm", "--communication-model",
                                                              type=str,
                                                              choices=CommunicationModel.available_models(),
                                                              required=True,
                                                              help="The communication model used to model the link quality between nodes. Typically low-asymmetry should be used."),

    "noise model":         lambda x, **kwargs: x.add_argument("-nm", "--noise-model",
                                                              type=str,
                                                              choices=NoiseModel.available_models(),
                                                              required=True,
                                                              help="Model the background noise in the network. meyer-heavy has high noise, casino-lab has lower noise. See models/noise for ways to graph the noisiness of these models."),

    # Only for Avrora
    "avrora":              _add_avrora_radio_model,

    # Only for Cooja
    "cooja":               _add_cooja_radio_model,

    "cooja profile":       lambda x, **kwargs: x.add_argument("--cooja-profile",
                                                              type=str,
                                                              choices=("hprof", "async-profiler", "yourkit"),
                                                              required=True,
                                                              help="Profile cooja execution"),

    "show raw log":        lambda x, **kwargs: x.add_argument("--show-raw-log",
                                                              action="store_true",
                                                              default=False,
                                                              help="Show all the log output as the simulation is running"),

    "attacker model":      lambda x, **kwargs: x.add_argument("-am", "--attacker-model",
                                                              type=AttackerConfiguration.eval_input,
                                                              choices=AttackerConfiguration.available_models(),
                                                              required=True,
                                                              help="The type of attacker that will try to find the source."),

    "fault model":         lambda x, **kwargs: x.add_argument("-fm", "--fault-model",
                                                              type=FaultModel.eval_input,
                                                              choices=FaultModel.available_models(),
                                                              required=False,
                                                              default=FaultModel.ReliableFaultModel(),
                                                              help="Specify if any faults will occur during program execution. By default no unexpected faults will occur."),

    "start time":          lambda x, **kwargs: x.add_argument("-st", "--latest-node-start-time",
                                                              type=ArgumentsCommon.type_positive_float,
                                                              required=False,
                                                              default=1.0,
                                                              help="Used to specify the latest possible start time in seconds. Start times will be chosen in the inclusive random range [0, x] where x is the value specified."),

    # Only for nodes with a CC2420
    "cc2420":              _add_cc2420,

    "gui node label":      lambda x, **kwargs: x.add_argument("--gui-node-label",
                                                              type=str,
                                                              required=False,
                                                              default=None),

    "gui scale":           lambda x, **kwargs: x.add_argument("--gui-scale",
                                                              type=ArgumentsCommon.type_positive_float,
                                                              required=False,
                                                              default=6),

    "gui timescale":       lambda x, **kwargs: x.add_argument("--gui-timescale",
                                                              type=ArgumentsCommon.type_positive_float,
                                                              required=False,
                                                              default=1.0),

    "job size":            lambda x, **kwargs: x.add_argument("--job-size",
                                                              type=ArgumentsCommon.type_positive_int,
                                                              required=True),

    "thread count":        lambda x, **kwargs: x.add_argument("--thread-count",
                                                              type=ArgumentsCommon.type_positive_int,
                                                              default=None),

    "job id":              lambda x, **kwargs: x.add_argument("--job-id",
                                                              type=ArgumentsCommon.type_positive_int,
                                                              default=None,
                                                              help="Used to pass the array id when this job has been submitted as a job array to the cluster."),

    "log file":            lambda x, **kwargs: x.add_argument("--log-file",
                                                              type=str,
                                                              nargs="+",
                                                              metavar="F",
                                                              required=True),

    "nonstrict":           lambda x, **kwargs: x.add_argument("--non-strict",
                                                              required=False,
                                                              action="store_true",
                                                              default=False),

    "extra metrics":       lambda x, **kwargs: x.add_argument("--extra-metrics",
                                                              required=False,
                                                              nargs="+",
                                                              type=str,
                                                              choices=MetricsCommon.EXTRA_METRICS_CHOICES,
                                                              default=None),

    "log converter":       _add_log_converter,

    "low power listening": _add_low_power_listening,
}

class CustomHelpFormatter(argparse.HelpFormatter):
    """Only show the arguments for the long argument."""
    def _format_action_invocation(self, action):
        if not action.option_strings:
            metavar, = self._metavar_formatter(action, action.dest)(1)
            return metavar

        else:
            parts = []

            # if the Optional doesn't take a value, format is:
            #    -s, --long
            if action.nargs == 0:
                parts.extend(action.option_strings)

            # if the Optional takes a value, format is:
            #    -s, --long ARGS
            else:
                default = action.dest.upper()
                args_string = self._format_args(action, default)
                parts.extend(action.option_strings[:-1])
                parts.append('%s %s' % (action.option_strings[-1], args_string))

            return ', '.join(parts)

class ArgumentsCommon(object):
    def __init__(self, description, has_safety_period=False, has_safety_factor=False, lpl_parameters_mandatory=False):
        self._parser = argparse.ArgumentParser(description=description, add_help=True)

        self._subparsers = {}

        simparsers = self._parser.add_subparsers(title="sim", dest="sim",
                                                 help="The tool you wish to use to run your algorithm.")

        for sim in submodule_loader.list_available(simulator.sim):

            self._subparsers[sim] = {}

            parser_sim = simparsers.add_parser(sim, add_help=True)

            subparsers = parser_sim.add_subparsers(title="mode", dest="mode",
                                                   help="The mode you wish to run the simulation in.")

            sim_mode = submodule_loader.load(simulator.sim, sim)
            for (mode, inherit, opts) in sim_mode.parsers():

                parents = (self._subparsers[sim][inherit],) if inherit is not None else tuple()

                parser_sub = subparsers.add_parser(mode, add_help=True, parents=parents,
                                                   conflict_handler='resolve',
                                                   formatter_class=CustomHelpFormatter)

                self._subparsers[sim][mode] = parser_sub

                for opt in opts:
                    OPTS[opt](parser_sub,
                              has_safety_period=has_safety_period,
                              has_safety_factor=has_safety_factor,
                              lpl_parameters_mandatory=lpl_parameters_mandatory,
                    )

        # Haven't parsed anything yet
        self.args = None

        # Don't show these arguments when printing the argument values before showing the results
        self.arguments_to_hide = {"job_id", "verbose", "low verbose", "debug", "gui_node_label", "gui_scale", "mode", "seed", "thread_count",
                                  "show_raw_log"}

    def add_argument(self, *args, **kwargs):
        for sim in self._subparsers:
            if sim == "offline":
                continue

            for parser in self._subparsers[sim].values():
                parser.add_argument(*args, **kwargs)

    def parse(self, argv):
        self.args = self._parser.parse_args(argv)

        if hasattr(self.args, 'seed'):
            if self.args.seed is None:
                self.args.seed = _secure_random()

        if hasattr(self.args, 'source_mobility'):
            configuration = Configuration.create(self.args.configuration, self.args)
            self.args.source_mobility.setup(configuration)

        # Some algorithm need to calculate parameters though some means
        # If so then we need to set those calculated parameters
        virtual_args = self.virtual_arguments()

        for (k, v) in virtual_args.items():
            setattr(self.args, k, v)

        return self.args

    def virtual_arguments(self):
        """Override this function to return virtual arguments
        that are not provided by the user, but instead calculated
        from other parameters."""
        return {}

    def build_arguments(self):
        result = {}

        # WARNING
        # All node ids passed to the simulation MUST be topology ids!

        #if hasattr(self.args, 'seed'):
        #  result["SLP_SEED"] = "UINT32_C({})".format(self.args.seed)

        if self.args.verbose:
            result["SLP_VERBOSE_DEBUG"] = 1

        if hasattr(self.args, "debug") and self.args.debug:
            result["SLP_DEBUG"] = 1

        # Only enable things like LEDS for the cases that we will use them
        # We could enable them for the testbed, but we get better reliability and performance by not doing so
        if self.args.mode == "GUI":
            result["SLP_USES_GUI_OUPUT"] = 1

        if hasattr(self.args, "attacker_model"):
            result.update(self.args.attacker_model.build_arguments())
        else:
            result.update(AttackerConfiguration.AttackerConfiguration.generic_build_arguments())

        # Source period could either be a float or a class derived from PeriodModel
        if hasattr(self.args, 'source_period'):
            if isinstance(self.args.source_period, float):
                if float(self.args.source_period) <= 0:
                    raise RuntimeError(f"The source_period ({self.args.source_period}) needs to be greater than 0")

                result["SOURCE_PERIOD_MS"] = int(self.args.source_period * 1000)
            elif isinstance(self.args.source_period, SourcePeriodModel.PeriodModel):
                result.update(self.args.source_period.build_arguments())
            else:
                raise RuntimeError(f"The source_period ({self.args.source_period}) either needs to be a float or an instance of SourcePeriodModel.PeriodModel")

        if hasattr(self.args, 'source_mobility'):
            result.update(self.args.source_mobility.build_arguments())
        else:
            # If there are no mobility models provided, then the only source specified
            # by the configuration can be used instead.
            # This is mainly for legacy algorithm support, StationaryMobilityModels
            # are a better choice for new algorithms.

            configuration = Configuration.create(self.args.configuration, self.args)

            if len(configuration.source_ids) != 1:
                raise RuntimeError(f"Invalid number of source ids in configuration {configuration}, there must be exactly one.")

            (source_id,) = configuration.source_ids

            result["SOURCE_NODE_ID"] = configuration.topology.o2t(source_id)

        if hasattr(self.args, 'fault_model'):
            result.update(self.args.fault_model.build_arguments())

        if hasattr(self.args, 'low_power_listening'):

            if self.args.low_power_listening == "enabled":
                result["LOW_POWER_LISTENING"] = 1

                if self.args.lpl_custom is not None:
                    result["CUSTOM_LOW_POWER_LISTENING"] = self.args.lpl_custom

                # See SystemLowPowerListeningP.nc for how this macro is used
                if self.args.lpl_remote_wakeup is not None:
                    result["LPL_DEF_REMOTE_WAKEUP"] = self.args.lpl_remote_wakeup

                # See PowerCycleP.nc for how this macro is used
                if self.args.lpl_local_wakeup is not None:
                    result["LPL_DEF_LOCAL_WAKEUP"] = self.args.lpl_local_wakeup

                # See SystemLowPowerListeningP.nc for how this macro is used
                if self.args.lpl_delay_after_receive is not None:
                    result["DELAY_AFTER_RECEIVE"] = self.args.lpl_delay_after_receive

                # See DefaultLpl.h for definition
                #
                # Other values than the default might be good.
                # The following link recommends 1600
                # See http://mail.millennium.berkeley.edu/pipermail/tinyos-help/2011-June/051478.html
                if self.args.lpl_max_cca_checks is not None:
                    result["MAX_LPL_CCA_CHECKS"] = self.args.lpl_max_cca_checks

                # Possibly worth increasing?
                # https://www.millennium.berkeley.edu/pipermail/tinyos-help/2011-August/052116.html
                if self.args.lpl_min_samples_before_detect is not None:
                    result["MIN_SAMPLES_BEFORE_DETECT"] = self.args.lpl_min_samples_before_detect

        if hasattr(self.args, 'rf_power'):
            if self.args.rf_power is not None:
                # TODO: consider setting the values for alternate drivers (CC2420X, ...)
                result['CC2420_DEF_RFPOWER'] = self.args.rf_power

        if hasattr(self.args, 'channel'):
            if self.args.channel is not None:
                result["CC2420_DEF_CHANNEL"] = self.args.channel

        if hasattr(self.args, 'acks'):
            if self.args.acks == "none":
                result["CC2420_NO_ACKNOWLEDGEMENTS"] = 1
            elif self.args.acks == "hardware":
                result["CC2420_HW_ACKNOWLEDGEMENTS"] = 1

                if self.args.address_recognition != "hardware":
                    raise RuntimeError("Hardware acks implies hardware address recognition")

            else:
                assert self.args.acks == "software"

        if hasattr(self.args, 'address_recognition'):
            if self.args.address_recognition == "none":
                result["CC2420_NO_ADDRESS_RECOGNITION"] = 1
            elif self.args.address_recognition == "hardware":
                result["CC2420_HW_ADDRESS_RECOGNITION"] = 1
            else:
                assert self.args.address_recognition == "software"

        # Some metrics class have build arguments, so we need to pull them in here:
        package = self.__module__.rsplit(".", 1)[0]
        algorithm_module = algorithm.import_algorithm(package, extras=["Metrics"])
        result.update(algorithm_module.Metrics.Metrics.build_arguments())

        # Pull in any build options from extra_metrics
        if hasattr(self.args, "extra_metrics") and self.args.extra_metrics is not None:
            # Build arguments from any extra metrics being used
            extra_metric_classes = [cls for cls in MetricsCommon.EXTRA_METRICS if cls.__name__ in self.args.extra_metrics]
            for extra_metric in extra_metric_classes:
                result.update(extra_metric.build_arguments())

        return result

    def _get_node_id(self, topo_node_id_str):
        """Gets the topology node id from a node id string.
        This value could either be the topology node id as an integer,
        or it could be an attribute of the topology or configuration (e.g., 'sink_id')."""
        configuration = Configuration.create(self.args.configuration, self.args)

        return configuration.get_node_id(topo_node_id_str)

    @staticmethod
    def type_probability(x):
        x = float(x)
        if x < 0.0 or x > 1.0:
            raise argparse.ArgumentTypeError(f"{x} not in range [0.0, 1.0]")
        return x

    @staticmethod
    def type_positive_int(x):
        x = int(x)
        if x < 0:
            raise argparse.ArgumentTypeError(f"{x} must be positive")
        return x

    @staticmethod
    def type_positive_float(x):
        x = float(x)
        if x < 0:
            raise argparse.ArgumentTypeError(f"{x} must be positive")
        return x

    @staticmethod
    def type_deviation(x):
        x = float(x)
        if x <= 0.0 or x > 1.0:
            raise argparse.ArgumentTypeError(f"{x} not in range (0.0, 1.0]")
        return x
