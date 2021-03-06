
from datetime import timedelta
import itertools

import simulator.sim
from simulator import CommandLineCommon

import algorithm
protectionless = algorithm.import_algorithm("protectionless")

from data import submodule_loader
from data.util import scalar_extractor

# Use the safety periods for SeqNosReactiveAttacker() if none are available for SeqNosOOOReactiveAttacker()
safety_period_equivalence = {
    "attacker model": {"SeqNosOOOReactiveAttacker()": "SeqNosReactiveAttacker()",
                       "SeqNosOOOReactiveAttacker(message_detect='within_range(4.75)')": "SeqNosReactiveAttacker(message_detect='within_range(4.75)')"}
}

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(protectionless.name, safety_period_equivalence=safety_period_equivalence)

        subparser = self._add_argument("table", self._run_table)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser.add_argument("--show", action="store_true", default=False)

        subparser = self._add_argument("graph", self._run_graph)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")

    def _argument_product(self, sim, extras=None):
        parameters = self.algorithm_module.Parameters

        parameter_values = self._get_global_parameter_values(sim, parameters)
        parameter_values.append(parameters.buffer_sizes)
        parameter_values.append(parameters.max_walk_lengths)
        parameter_values.append(parameters.direct_to_sink_prs)
        parameter_values.append(parameters.msg_group_sizes)

        argument_product = list(itertools.product(*parameter_values))

        argument_product = self.add_extra_arguments(argument_product, extras)

        #argument_product = self.adjust_source_period_for_multi_source(sim, argument_product)
        
        return argument_product

    def time_after_first_normal_to_safety_period(self, tafn):
        return tafn * 2.0

    def _cluster_time_estimator(self, sim, args, **kwargs):
        historical_key_names = ('configuration', 'network size', 'source period')

        if sim == "tossim":
            historical = {
                ('RandomPoissonDiskConnectedSeed2', '11', '0.25'): timedelta(seconds=3),
                ('RandomPoissonDiskConnectedSeed2', '11', '0.5'): timedelta(seconds=3),
                ('RandomPoissonDiskConnectedSeed2', '11', '1.0'): timedelta(seconds=4),
                ('RandomPoissonDiskConnectedSeed2', '11', '2.0'): timedelta(seconds=4),
                ('RandomPoissonDiskConnectedSeed2', '15', '0.25'): timedelta(seconds=12),
                ('RandomPoissonDiskConnectedSeed2', '15', '0.5'): timedelta(seconds=12),
                ('RandomPoissonDiskConnectedSeed2', '15', '1.0'): timedelta(seconds=14),
                ('RandomPoissonDiskConnectedSeed2', '15', '2.0'): timedelta(seconds=16),
                ('RandomPoissonDiskConnectedSeed2', '7', '0.25'): timedelta(seconds=2),
                ('RandomPoissonDiskConnectedSeed2', '7', '0.5'): timedelta(seconds=2),
                ('RandomPoissonDiskConnectedSeed2', '7', '1.0'): timedelta(seconds=2),
                ('RandomPoissonDiskConnectedSeed2', '7', '2.0'): timedelta(seconds=2),
                ('SourceCorner', '11', '0.25'): timedelta(seconds=5),
                ('SourceCorner', '11', '0.5'): timedelta(seconds=6),
                ('SourceCorner', '11', '1.0'): timedelta(seconds=7),
                ('SourceCorner', '11', '2.0'): timedelta(seconds=7),
                ('SourceCorner', '15', '0.25'): timedelta(seconds=11),
                ('SourceCorner', '15', '0.5'): timedelta(seconds=12),
                ('SourceCorner', '15', '1.0'): timedelta(seconds=14),
                ('SourceCorner', '15', '2.0'): timedelta(seconds=17),
                ('SourceCorner', '21', '0.25'): timedelta(seconds=31),
                ('SourceCorner', '21', '0.5'): timedelta(seconds=33),
                ('SourceCorner', '21', '1.0'): timedelta(seconds=38),
                ('SourceCorner', '21', '2.0'): timedelta(seconds=46),
                ('SourceCorner', '25', '0.25'): timedelta(seconds=57),
                ('SourceCorner', '25', '0.5'): timedelta(seconds=61),
                ('SourceCorner', '25', '1.0'): timedelta(seconds=69),
                ('SourceCorner', '25', '2.0'): timedelta(seconds=83),
                ('SourceCorner', '7', '0.25'): timedelta(seconds=2),
                ('SourceCorner', '7', '0.5'): timedelta(seconds=2),
                ('SourceCorner', '7', '1.0'): timedelta(seconds=2),
                ('SourceCorner', '7', '2.0'): timedelta(seconds=3),
            }

        else:
            historical = {}

        return self._cluster_time_estimator_from_historical(
            sim, args, kwargs, historical_key_names, historical,
            allowance=0.35,
            max_time=timedelta(days=2)
        )

    def _run_table(self, args):
        from data.table.summary_formatter import TableDataFormatter
        fmt = TableDataFormatter()

        parameters = [
            'received ratio',
            'captured',
            'normal latency',
            'norm(sent,time taken)',
            'attacker distance',
        ]

        def results_filter(params):
            return params["noise model"] != "casino-lab" or params["pr direct to sink"] != "0.2"

        hide_parameters = ['buffer size', 'max walk length', 'pr direct to sink']
 
        extractors = {
            # Just get the distance of attacker 0 from node 0 (the source in SourceCorner)
            "attacker distance": lambda yvalue: yvalue[(0, 0)]
        }

        self._create_results_table(args.sim, parameters,
            fmt=fmt, results_filter=results_filter, hide_parameters=hide_parameters, extractors=extractors,
            show=args.show)

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (seconds)', 'left top'),
            #'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            #'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'norm(sent,time taken)': ('Total Messages Sent per Second', 'left top'),
            'attacker distance': ('Attacker-Source Distance (Meters)', 'left top'),
            #"attacker distance percentage": ('Normalised Attacker Distance (%)', 'left top'),
            #'failed avoid sink': ('Failed to Avoid Sink (%)', 'left top'),
            #'failed avoid sink when captured': ('Failed to Avoid Sink When Captured (%)', 'left top'),
        }

        varying = [
            #(('network size', ''), ('msg group size', '')),
            (('pr direct to sink', ''), ('msg group size', '')),
            #(('network size', ''), ('source period', ' seconds')),
            #(('network size', ''), ('pr direct to sink', '')),
        ]

        custom_yaxis_range_max = {
            'received ratio': 100,
            'norm(sent,time taken)': 500,
            'captured': 25,
            'normal latency': 4000,
            'attacker distance': 80,
        }            

        yextractors = {
            # Just get the distance of attacker 0 from node 0 (the source in SourceCorner)
            "attacker distance": lambda yvalue: scalar_extractor(yvalue, key=(0, 0)),
            "attacker distance percentage": lambda yvalue: scalar_extractor(yvalue, key=(0, 0)) * 100
        }

        kwargs = {
            "custom_yaxis_range_max": custom_yaxis_range_max,
            "yextractor": yextractors,
            "xaxis_font": "',16'",
            "yaxis_font": "',16'",
            "xlabel_font": "',14'",
            "ylabel_font": "',14'",
            "line_width": 3,
            "point_size": 1,
            "nokey": True,
            "generate_legend_graph": True,
            "legend_font_size": 16,
        }

        self._create_versus_graph(args.sim, graph_parameters, varying, **kwargs)

        varying = [
            (('network size', ''), ('msg group size', '')),
        ]

        kwargs["xvalues_to_tic_label"] = lambda x: f'{x}x{x}'

        self._create_versus_graph(args.sim, graph_parameters, varying, **kwargs)
